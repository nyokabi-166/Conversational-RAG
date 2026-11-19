"""Build the packaged corpus vocabulary used by the answerability guard.

The vocabulary is the set of normalized stems of every verified policy chunk in
the index. The guard refuses a question only when a distinctive term is missing
from this set, so it must be rebuilt whenever the knowledge base changes.

Usage (from the repository root):
    backend\\.venv\\Scripts\\python.exe backend\\scripts\\build_corpus_vocabulary.py
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from langchain_chroma import Chroma

from src.modules.answer_quality import corpus_term_set
from src.modules.policy_sources import is_verified_policy_source
from src.rag_pipeline import MiniLMEmbeddings

DEFAULT_INDEX = BACKEND_DIR / "data" / "chroma_db"
DEFAULT_OUTPUT = BACKEND_DIR / "src" / "modules" / "corpus_vocabulary.json"


def build(index_dir: Path, include_unverified: bool = False) -> dict:
    store = Chroma(
        persist_directory=str(index_dir), embedding_function=MiniLMEmbeddings()
    )
    data = store.get(include=["documents", "metadatas"])
    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []

    texts = []
    sources = set()
    for content, metadata in zip(documents, metadatas):
        if not content:
            continue
        metadata = metadata or {}
        source = metadata.get("source", "")
        if not include_unverified and not is_verified_policy_source(source):
            continue
        texts.append(content)
        if source:
            sources.add(source)

    normalized = sorted(" ".join(text.split()) for text in texts)
    digest = hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "index_dir": str(index_dir),
        "chunk_count": len(texts),
        "source_count": len(sources),
        "content_sha256": digest,
        "terms": sorted(corpus_term_set(texts)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include chunks from sources the retrieval filter would exclude.",
    )
    args = parser.parse_args()

    payload = build(args.index_dir, args.include_unverified)
    if not payload["terms"]:
        print(f"No terms found in {args.index_dir}; refusing to write an empty vocabulary.")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(payload['terms'])} terms from {payload['chunk_count']} chunks "
        f"({payload['source_count']} sources) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
