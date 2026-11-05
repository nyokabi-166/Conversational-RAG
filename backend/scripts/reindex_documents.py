"""Rebuild policy chunks from uploaded source files using current parsing rules."""

from pathlib import Path

from langchain_chroma import Chroma

from src.modules.load_vesctorstore import (
    PERSIST_DIR,
    UPLOAD_DIR,
    PreparedUpload,
    load_vectorstore,
)
from src.modules.policy_sources import (
    UNVERIFIED_POLICY_SOURCES,
    is_verified_policy_source,
)
from src.rag_pipeline import MiniLMEmbeddings


def _source_name(path: Path) -> str:
    """Remove the UUID prefix used for stored uploads, when present."""
    prefix, separator, name = path.name.partition("_")
    if separator and len(prefix) == 32 and all(
        character in "0123456789abcdef" for character in prefix.lower()
    ):
        return name
    return path.name


def main() -> None:
    upload_dir = Path(UPLOAD_DIR)
    newest_by_source = {}
    for path in upload_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {".pdf", ".html", ".htm"}:
            source_name = _source_name(path)
            if source_name.casefold() in {
                name.casefold() for name in UNVERIFIED_POLICY_SOURCES
            }:
                continue
            previous = newest_by_source.get(source_name)
            if previous is None or path.stat().st_mtime > previous.stat().st_mtime:
                newest_by_source[source_name] = path

    if not newest_by_source:
        raise SystemExit(f"No uploaded PDF or HTML sources found in {upload_dir}.")

    # Keep original files for review, but remove explicitly unverified PDF chunks
    # from the active search index before the curated sources are reindexed.
    embeddings = MiniLMEmbeddings()
    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
    )
    indexed = vectorstore.get(include=["metadatas"])
    stale_ids = [
        document_id
        for document_id, metadata in zip(
            indexed.get("ids") or [], indexed.get("metadatas") or []
        )
        if not is_verified_policy_source((metadata or {}).get("source"))
    ]
    if stale_ids:
        vectorstore.delete(ids=stale_ids)
    print(
        "Removed unverified sources from the active index: "
        + ", ".join(sorted(UNVERIFIED_POLICY_SOURCES))
    )

    reindexed = []
    skipped = []
    for name, path in sorted(newest_by_source.items()):
        upload = PreparedUpload(filename=name, content=path.read_bytes())
        try:
            reindexed.extend(load_vectorstore([upload], embedding_function=embeddings))
        except Exception as exc:
            skipped.append((name, str(exc)))

    print(f"Reindexed {len(reindexed)} source documents:")
    for name, chunk_count in reindexed:
        print(f"- {name}: {chunk_count} chunks")
    for name, reason in skipped:
        print(f"Skipped {name}: {reason}")
    if not reindexed:
        raise SystemExit("No source documents could be reindexed.")


if __name__ == "__main__":
    main()
