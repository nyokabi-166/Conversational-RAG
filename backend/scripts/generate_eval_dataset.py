"""Generate an AI-drafted evaluation dataset from the indexed policy corpus."""

import argparse
import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from evaluate_rag import BACKEND_DIR, load_vectorstore
from langchain_core.documents import Document

load_dotenv(BACKEND_DIR / ".env")


def _first_value(row: dict, names: tuple[str, ...]) -> str:
    """Return the first non-empty value in a row, handling pandas nulls."""
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value).strip()
    return ""


def generate_dataset(size: int, output_path: Path) -> None:
    """Create a RAGAS synthetic test set from this project's indexed Chroma data."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set GEMINI_API_KEY in backend/.env before generating the draft dataset."
        )

    try:
        from google import genai
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import llm_factory
        from ragas.testset import TestsetGenerator

        from src.rag_pipeline import MiniLMEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Follow backend/evaluation/README.md."
        ) from exc

    vectorstore = load_vectorstore()
    stored = vectorstore.get(include=["documents", "metadatas"])
    documents = [
        Document(page_content=text, metadata=metadata or {})
        for text, metadata in zip(
            stored.get("documents", []), stored.get("metadatas", [])
        )
        if text and text.strip()
    ]
    if not documents:
        raise RuntimeError(
            "No indexed policy chunks were found. Upload and index the Kenya Airways "
            "documents through the backend first."
        )

    model_name = os.getenv("GEMINI_TESTSET_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    generator_llm = llm_factory(model_name, provider="google", client=client)
    generator_embeddings = LangchainEmbeddingsWrapper(MiniLMEmbeddings())
    generator = TestsetGenerator(
        llm=generator_llm,
        embedding_model=generator_embeddings,
    )
    generated = generator.generate_with_langchain_docs(
        documents,
        testset_size=size,
    )

    draft_rows = []
    for generated_row in generated.to_pandas().to_dict(orient="records"):
        question = _first_value(generated_row, ("user_input", "question"))
        ground_truth = _first_value(
            generated_row, ("reference", "ground_truth", "reference_answer")
        )
        if not question or not ground_truth:
            continue
        source_contexts = _first_value(
            generated_row, ("reference_contexts", "contexts")
        )
        draft_rows.append(
            {
                "question": question,
                "ground_truth": ground_truth,
                "source_contexts": source_contexts,
                "review_status": "UNREVIEWED - AI generated",
            }
        )

    if not draft_rows:
        raise RuntimeError(
            "RAGAS generated rows, but the question/reference columns could not be "
            "mapped. Inspect the RAGAS output schema before evaluating."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=draft_rows[0].keys())
        writer.writeheader()
        writer.writerows(draft_rows)

    print(f"Generated {len(draft_rows)} draft questions from {len(documents)} chunks.")
    print(f"Review every row before using it: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "evaluation" / "generated_dataset_draft.csv",
    )
    args = parser.parse_args()
    if args.size < 1:
        parser.error("--size must be at least 1")
    generate_dataset(args.size, args.output)


if __name__ == "__main__":
    main()
