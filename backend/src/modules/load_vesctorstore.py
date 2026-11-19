"""Document validation, ingestion, and ChromaDB vector store management."""

import os
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile
from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.modules.policy_sources import UNVERIFIED_POLICY_SOURCES
from src.rag_pipeline import MiniLMEmbeddings

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db")
UPLOAD_DIR = os.getenv("UPLOAD_DIRECTORY", "./uploads")
SOURCE_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "source_catalog.json"
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_FILES = 10
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)

_SOURCE_CATALOG_CACHE: Optional[dict] = None


def load_source_catalog() -> dict:
    """Return {filename: {title, url}} from the packaged source catalog."""
    global _SOURCE_CATALOG_CACHE
    if _SOURCE_CATALOG_CACHE is None:
        catalog: dict = {}
        try:
            import json

            raw = json.loads(SOURCE_CATALOG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                catalog = raw
        except (OSError, ValueError):
            catalog = {}
        _SOURCE_CATALOG_CACHE = catalog
    return _SOURCE_CATALOG_CACHE


def source_catalog_entry(filename: str) -> dict:
    """Look up {title, url} for a source filename; empty dict when unknown."""
    name = (filename or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    entry = load_source_catalog().get(name)
    return entry if isinstance(entry, dict) else {}


class UploadValidationError(ValueError):
    """A client upload that does not meet the supported file constraints."""

    def __init__(
        self,
        message: str,
        filename: str,
        status_code: int = 400,
        file_size_bytes: Optional[int] = None,
    ):
        super().__init__(message)
        self.filename = filename
        self.status_code = status_code
        self.file_size_bytes = file_size_bytes


@dataclass(frozen=True)
class PreparedUpload:
    """Validated upload data with a safe display filename."""

    filename: str
    content: bytes


class _HTMLTextExtractor(HTMLParser):
    """Extract page text: keep <main> content only, drop site chrome, preserve tables.

    Chrome dropped: scripts/styles, nav/footer/aside, the site header outside
    <main>, and elements whose class/id looks like a cookie banner, consent
    dialog, skip link, mobile menu, popup, modal, or browser-compat notice.
    When the page has a <main> element its text is preferred over the rest.
    Table rows keep the "Header: value | ..." joining from the original
    extractor so allowance tables stay readable for the LLM.
    """

    _IGNORED_TAGS = {
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "template",
        "nav",
        "footer",
        "aside",
    }
    _CHROME_HINTS = (
        "cookie",
        "consent",
        "skip-to",
        "mobile-menu",
        "popup-",
        "modal-",
        "browser-compatibility",
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._main_parts: List[str] = []
        self._saw_main = False
        self._in_main = 0
        self._skip_stack: List[str] = []
        self._table_depth = 0
        self._table_headers: Optional[List[str]] = None
        self._current_row: Optional[List[str]] = None
        self._current_cell: Optional[List[str]] = None
        self._row_has_header_cells = False
        self.title: Optional[str] = None
        self.canonical_url: Optional[str] = None
        self._in_title = False

    @property
    def _sink(self) -> List[str]:
        return self._main_parts if self._in_main else self.parts

    def _is_chrome(self, tag: str, attrs) -> bool:
        if tag in self._IGNORED_TAGS:
            return True
        if tag == "header" and not self._in_main:
            return True
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        hint_text = (
            f"{attr_map.get('class', '')} {attr_map.get('id', '')}"
        ).casefold()
        return any(hint in hint_text for hint in self._CHROME_HINTS)

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag == "main":
            self._in_main += 1
            self._saw_main = True
        if tag == "title":
            self._in_title = True
        if tag == "link":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            if attr_map.get("rel", "").strip().casefold() == "canonical":
                href = attr_map.get("href", "").strip()
                if href and not self.canonical_url:
                    self.canonical_url = href
        if self._is_chrome(tag, attrs):
            self._skip_stack.append(tag)
            return
        if self._skip_stack:
            return
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._table_headers = None
                self._sink.append("\n")
        elif self._table_depth:
            if tag == "tr":
                self._current_row = []
                self._row_has_header_cells = False
            elif tag in {"td", "th"}:
                self._current_cell = []
                self._row_has_header_cells |= tag == "th"
        elif tag in {"br", "p", "div", "li", "h1", "h2", "h3"}:
            self._sink.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "main" and self._in_main:
            self._in_main -= 1
        if self._skip_stack:
            if tag == self._skip_stack[-1]:
                self._skip_stack.pop()
            elif tag in self._skip_stack:
                while self._skip_stack and self._skip_stack[-1] != tag:
                    self._skip_stack.pop()
                if self._skip_stack:
                    self._skip_stack.pop()
            return
        if (
            self._table_depth and tag in {"td", "th"} and self._current_cell is not None
        ):
            cell_text = " ".join(" ".join(self._current_cell).split())
            if self._current_row is not None:
                self._current_row.append(cell_text)
            self._current_cell = None
        elif self._table_depth and tag == "tr" and self._current_row:
            row = [cell for cell in self._current_row if cell]
            if row:
                row_text = " ".join(row).casefold()
                is_header = self._row_has_header_cells or (
                    "routing" in row_text
                    and ("business" in row_text or "economy" in row_text)
                )
                if is_header:
                    self._table_headers = row
                elif self._table_headers and len(self._table_headers) == len(row):
                    row = [
                        f"{header}: {value}"
                        for header, value in zip(self._table_headers, row)
                    ]
                self._sink.extend(["\n", " | ".join(row), "\n"])
            self._current_row = None
            self._row_has_header_cells = False
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0:
                self._sink.append("\n")
        elif not self._table_depth and tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self._sink.append("\n")

    def handle_data(self, data: str):
        if self._in_title:
            if self.title is None:
                self.title = data.strip()
            else:
                self.title = f"{self.title}{data}".strip()
            return
        if self._skip_stack or not data.strip():
            return
        if self._current_cell is not None:
            self._current_cell.append(data.strip())
        else:
            self._sink.append(data)

    def get_text(self) -> str:
        """Return preferred text: <main> content when present, else the rest."""
        source = self._main_parts if (self._saw_main and self._main_parts) else self.parts
        raw = "".join(source)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(self._strip_page_footer(lines))

    # Lines that open the closing footer of every Kenya Airways page: the newsletter
    # sign-up form and the "related policies" link list. Nothing after them is policy.
    _FOOTER_MARKERS = ("get the latest offers", "related policies")

    @classmethod
    def _strip_page_footer(cls, lines: List[str]) -> List[str]:
        """Drop the newsletter/related-links footer that closes each page."""
        for index in range(len(lines) - 1, -1, -1):
            if (
                lines[index].casefold() in cls._FOOTER_MARKERS
                and index >= len(lines) - 12
            ):
                return lines[:index]
        return lines


def _safe_display_filename(filename: str) -> str:
    """Strip path components and control characters from a client filename."""
    basename = filename.replace("\\", "/").split("/")[-1]
    basename = "".join(character for character in basename if character.isprintable())
    basename = basename.strip().strip(".")
    if not basename or basename in {".", ".."}:
        raise UploadValidationError("A valid filename is required.", "(unnamed)")
    return basename[:200]


def validate_uploaded_files(files: List[UploadFile]) -> List[PreparedUpload]:
    """Validate supported file types, per-file size, and total request size."""
    if not files:
        raise UploadValidationError("At least one document is required.", "(unnamed)")
    if len(files) > MAX_UPLOAD_FILES:
        raise UploadValidationError(
            f"A maximum of {MAX_UPLOAD_FILES} documents may be uploaded at once.",
            "(multiple files)",
        )

    prepared: List[PreparedUpload] = []
    total_size = 0
    for upload in files:
        original_name = _safe_display_filename(upload.filename or "")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UploadValidationError(
                "Only PDF and HTML documents are supported.",
                original_name,
                file_size_bytes=getattr(upload, "size", None),
            )

        content = upload.file.read(MAX_UPLOAD_SIZE_BYTES + 1)
        upload.file.seek(0)
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise UploadValidationError(
                "Each document must be 20 MB or smaller.",
                original_name,
                413,
                len(content),
            )
        if not content:
            raise UploadValidationError(
                "The uploaded document is empty.",
                original_name,
                file_size_bytes=0,
            )

        total_size += len(content)
        if total_size > MAX_TOTAL_UPLOAD_SIZE_BYTES:
            raise UploadValidationError(
                "The combined upload size must be 50 MB or smaller.",
                original_name,
                413,
                len(content),
            )

        if extension == ".pdf" and b"%PDF-" not in content[:1024]:
            raise UploadValidationError(
                "The uploaded PDF does not have a valid PDF header.",
                original_name,
                file_size_bytes=len(content),
            )
        if extension in {".html", ".htm"}:
            try:
                content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise UploadValidationError(
                    "HTML documents must be UTF-8 encoded text.",
                    original_name,
                    file_size_bytes=len(content),
                ) from exc

        prepared.append(PreparedUpload(filename=original_name, content=content))

    return prepared


def _load_html_document(path: str, display_name: str) -> Document:
    """Load HTML as main-content text with title/url metadata (chrome dropped)."""
    content = Path(path).read_text(encoding="utf-8-sig")
    extractor = _HTMLTextExtractor()
    extractor.feed(content)
    text = extractor.get_text()
    if not text:
        raise ValueError(f"No readable text could be extracted from {display_name}.")
    metadata = {"source": display_name}
    if extractor.title:
        metadata["title"] = extractor.title
    if extractor.canonical_url:
        metadata["url"] = extractor.canonical_url
    catalog = source_catalog_entry(display_name)
    metadata.setdefault("title", catalog.get("title", ""))
    metadata.setdefault("url", catalog.get("url", ""))
    metadata["title"] = metadata.get("title") or ""
    metadata["url"] = metadata.get("url") or ""
    return Document(page_content=text, metadata=metadata)


def load_vectorstore(
    uploaded_files: List[PreparedUpload],
    embedding_function=None,
) -> List[Tuple[str, int]]:
    """Index validated PDF/HTML uploads and return each filename's chunk count."""
    excluded_names = {name.casefold() for name in UNVERIFIED_POLICY_SOURCES}
    unverified = sorted(
        upload.filename
        for upload in uploaded_files
        if upload.filename.casefold() in excluded_names
    )
    if unverified:
        raise ValueError(
            "These sources are excluded until their official provenance is verified: "
            + ", ".join(unverified)
        )

    # These imports also load Transformers' package discovery; defer them until a
    # staff member actually submits a document for indexing.
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    all_chunks = []
    indexed_files: List[Tuple[str, int]] = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
    )

    for upload in uploaded_files:
        stored_name = f"{uuid.uuid4().hex}_{upload.filename}"
        stored_path = Path(UPLOAD_DIR) / stored_name
        stored_path.write_bytes(upload.content)

        if Path(upload.filename).suffix.lower() == ".pdf":
            documents = PyPDFLoader(str(stored_path)).load()
            catalog = source_catalog_entry(upload.filename)
            for document in documents:
                document.metadata["source"] = upload.filename
                document.metadata.setdefault("title", catalog.get("title", ""))
                document.metadata.setdefault("url", catalog.get("url", ""))
        else:
            documents = [_load_html_document(str(stored_path), upload.filename)]

        chunks = splitter.split_documents(documents)
        if not chunks:
            raise ValueError(
                f"No readable text could be extracted from {upload.filename}."
            )
        # Prepend a short page-title header to every chunk so retrieval and the
        # generator can tell which page a fragment came from even mid-chunk.
        for chunk in chunks:
            title = (chunk.metadata or {}).get("title") or ""
            title = str(title).strip()
            if title and not chunk.page_content.startswith(f"{title}\n"):
                chunk.page_content = f"{title}\n{chunk.page_content}"
        all_chunks.extend(chunks)
        indexed_files.append((upload.filename, len(chunks)))

    if not all_chunks:
        raise ValueError("No readable text could be extracted from the uploaded files.")

    embedding_function = embedding_function or MiniLMEmbeddings()
    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embedding_function,
    )
    source_names = sorted({upload.filename for upload in uploaded_files})
    vectorstore.delete(where={"source": {"$in": source_names}})
    vectorstore.add_documents(all_chunks)
    return indexed_files
