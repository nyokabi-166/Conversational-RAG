"""Document validation, ingestion, and ChromaDB vector store management."""

import os
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag_pipeline import MiniLMEmbeddings

PERSIST_DIR = "./data/chroma_db"
UPLOAD_DIR = "./uploads"
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_FILES = 10
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)


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
    """Extract readable text while ignoring script and style contents."""

    _IGNORED_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif tag.lower() in {"br", "p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())


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
    """Load HTML as text without executing embedded scripts or styles."""
    content = Path(path).read_text(encoding="utf-8-sig")
    extractor = _HTMLTextExtractor()
    extractor.feed(content)
    text = " ".join(" ".join(extractor.parts).split())
    if not text:
        raise ValueError(f"No readable text could be extracted from {display_name}.")
    return Document(page_content=text, metadata={"source": display_name})


def load_vectorstore(
    uploaded_files: List[PreparedUpload],
) -> List[Tuple[str, int]]:
    """Index validated PDF/HTML uploads and return each filename's chunk count."""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    all_chunks = []
    indexed_files: List[Tuple[str, int]] = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""],
    )

    for upload in uploaded_files:
        stored_name = f"{uuid.uuid4().hex}_{upload.filename}"
        stored_path = Path(UPLOAD_DIR) / stored_name
        stored_path.write_bytes(upload.content)

        if Path(upload.filename).suffix.lower() == ".pdf":
            documents = PyPDFLoader(str(stored_path)).load()
            for document in documents:
                document.metadata["source"] = upload.filename
        else:
            documents = [_load_html_document(str(stored_path), upload.filename)]

        chunks = splitter.split_documents(documents)
        if not chunks:
            raise ValueError(
                f"No readable text could be extracted from {upload.filename}."
            )
        all_chunks.extend(chunks)
        indexed_files.append((upload.filename, len(chunks)))

    if not all_chunks:
        raise ValueError("No readable text could be extracted from the uploaded files.")

    Chroma.from_documents(
        documents=all_chunks,
        embedding=MiniLMEmbeddings(),
        persist_directory=PERSIST_DIR,
    )
    return indexed_files
