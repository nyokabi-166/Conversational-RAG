"""Evaluate the RAG and no-retrieval baseline using the project's own backend."""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from langchain_chroma import Chroma  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from src.modules.llm import (  # noqa: E402
    get_chat_model,
    get_llm_chain,
    get_model_name,
    get_model_provider,
)
from src.modules.load_vesctorstore import PERSIST_DIR  # noqa: E402
from src.modules.query_handlers import query_chain  # noqa: E402
from src.rag_pipeline import MiniLMEmbeddings  # noqa: E402

DEFAULT_DATASET = BACKEND_DIR / "evaluation" / "dataset.csv"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "evaluation" / "results"
BASELINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an airline customer-support assistant. Answer using your "
            "general model knowledge only; no policy documents or retrieved "
            "context are provided. Be clear when you are uncertain and do not "
            "invent current airline-specific rules.",
        ),
        ("human", "{question}"),
    ]
)


def read_dataset(path: Path, limit: int | None) -> list[dict[str, str]]:
    """Read the fixed question and reference-answer CSV used by both systems."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Create it from evaluation/dataset_template.csv first."
        )

    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as dataset_file:
        for line_number, row in enumerate(csv.DictReader(dataset_file), start=2):
            question = (row.get("question") or "").strip()
            ground_truth = (row.get("ground_truth") or "").strip()
            if not question and not ground_truth:
                continue
            if not question or not ground_truth:
                raise ValueError(
                    f"Row {line_number} needs both question and ground_truth."
                )
            rows.append({"question": question, "ground_truth": ground_truth})

    if not rows:
        raise ValueError(f"No complete question/answer rows found in {path}.")
    return rows[:limit] if limit else rows


def load_vectorstore() -> Chroma:
    """Load the same persisted Chroma collection and embeddings as the backend."""
    persist_path = BACKEND_DIR / PERSIST_DIR
    if not persist_path.is_dir() or not any(persist_path.iterdir()):
        raise FileNotFoundError(
            f"Chroma database not found at {persist_path}. "
            "Upload/index policy documents through the backend first."
        )
    return Chroma(
        persist_directory=str(persist_path),
        embedding_function=MiniLMEmbeddings(),
    )


def answer_with_rag(
    question: str, vectorstore: Chroma, chain: Any
) -> tuple[str, list[str]]:
    """Run retrieval and generation using the same path as the /ask endpoint."""
    # main.py uses k=4 for its production retrieval call.
    documents = vectorstore.similarity_search(question, k=4)
    context = "\n\n---\n\n".join(document.page_content for document in documents)
    result = query_chain(chain, question, context=context, source_docs=documents)
    if result.get("error"):
        raise RuntimeError(f"RAG generation failed: {result['error']}")
    return str(result.get("response", "")), [doc.page_content for doc in documents]


def answer_with_baseline(question: str, model: Any) -> str:
    """Run the same configured generation model without document retrieval."""
    answer = (BASELINE_PROMPT | model).invoke({"question": question})
    return str(getattr(answer, "content", answer))


def make_judge(model_name: str) -> Any:
    """Configure Gemini as the independent RAGAS judge, as specified in the paper."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set GEMINI_API_KEY in backend/.env to use Gemini as the RAGAS judge."
        )
    try:
        from google import genai
        from ragas.llms import llm_factory
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Install the evaluation group "
            "from backend/pyproject.toml."
        ) from exc

    return llm_factory(
        model_name,
        provider="google",
        client=genai.Client(api_key=api_key),
    )


def run_evaluation(dataset_rows: list[dict[str, str]], output_dir: Path) -> None:
    """Run both generation conditions and save per-question RAGAS scores."""
    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import (
            AnswerCorrectness,
            AnswerRelevancy,
            ContextRecall,
            Faithfulness,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Install the evaluation group "
            "from backend/pyproject.toml."
        ) from exc

    judge_name = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.8-flash")
    judge = make_judge(judge_name)
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    vectorstore = load_vectorstore()
    rag_chain = get_llm_chain()
    baseline_model = get_chat_model()

    rag_rows = []
    baseline_rows = []
    for index, row in enumerate(dataset_rows, start=1):
        question = row["question"]
        print(f"[{index}/{len(dataset_rows)}] Generating RAG and baseline answers")
        rag_answer, retrieved_contexts = answer_with_rag(
            question, vectorstore, rag_chain
        )
        baseline_answer = answer_with_baseline(question, baseline_model)
        rag_rows.append(
            {
                "question": question,
                "answer": rag_answer,
                "contexts": retrieved_contexts,
                "ground_truth": row["ground_truth"],
            }
        )
        baseline_rows.append(
            {
                "question": question,
                "answer": baseline_answer,
                # The baseline has no retrieved evidence by design.
                "contexts": [],
                "ground_truth": row["ground_truth"],
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    def shared_metrics():
        return [
            AnswerRelevancy(llm=judge, embeddings=judge_embeddings),
            AnswerCorrectness(llm=judge, embeddings=judge_embeddings),
        ]

    rag_metrics = [
        Faithfulness(llm=judge),
        ContextRecall(llm=judge),
        *shared_metrics(),
    ]

    rag_result = evaluate(Dataset.from_list(rag_rows), metrics=rag_metrics)
    baseline_result = evaluate(
        Dataset.from_list(baseline_rows), metrics=shared_metrics()
    )

    rag_frame = rag_result.to_pandas()
    rag_frame.insert(0, "system", "RAG")
    baseline_frame = baseline_result.to_pandas()
    baseline_frame.insert(0, "system", "Baseline")
    import pandas as pd

    combined = pd.concat([rag_frame, baseline_frame], ignore_index=True, sort=False)
    combined.to_csv(output_dir / "evaluation_report.csv", index=False)

    summary_columns = [
        column
        for column in (
            "faithfulness",
            "answer_relevancy",
            "context_recall",
            "answer_correctness",
        )
        if column in combined.columns
    ]
    print(f"\nGeneration model: {get_model_name()} ({get_model_provider()})")
    print(f"Judge model: {judge_name}")
    print(combined.groupby("system")[summary_columns].mean(numeric_only=True))
    print(f"\nSaved per-question scores to {output_dir / 'evaluation_report.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--limit", type=int, default=None, help="Run only the first N rows (demo mode)."
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    run_evaluation(read_dataset(args.dataset, args.limit), args.output_dir)


if __name__ == "__main__":
    main()
