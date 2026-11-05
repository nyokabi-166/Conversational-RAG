"""Evaluate the RAG and no-retrieval baseline using the project's own backend."""

import argparse
import csv
import math
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
from src.modules.query_handlers import (  # noqa: E402
    format_policy_context,
    query_chain,
    retrieve_policy_documents,
)
from src.rag_pipeline import MiniLMEmbeddings  # noqa: E402

DEFAULT_DATASET = BACKEND_DIR / "evaluation" / "dataset.csv"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "evaluation" / "results"
ANSWER_RELEVANCY_STRICTNESS = 1
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
            review_status = (row.get("review_status") or "").strip().lower()
            if "review_status" in row and review_status != "reviewed":
                raise ValueError(
                    f"Row {line_number} is not approved for evaluation. "
                    "Check the answer against its source, then set "
                    "review_status to 'reviewed'."
                )
            if not question or not ground_truth:
                raise ValueError(
                    f"Row {line_number} needs both question and ground_truth."
                )
            rows.append(
                {
                    "case_id": (row.get("case_id") or f"Q{len(rows) + 1:03d}").strip(),
                    "question": question,
                    "ground_truth": ground_truth,
                    "source_file": (row.get("source_file") or "").strip(),
                    "source_url": (row.get("source_url") or "").strip(),
                    "category": (row.get("category") or "uncategorized").strip(),
                    "answerability": (
                        row.get("answerability") or "unspecified"
                    ).strip(),
                }
            )

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
    """Run the same hybrid retrieval and generation path as the /ask endpoint."""
    documents = retrieve_policy_documents(vectorstore, question)
    context = format_policy_context(documents)
    result = query_chain(chain, question, context=context, source_docs=documents)
    if result.get("error"):
        raise RuntimeError(f"RAG generation failed: {result['error']}")
    return str(result.get("response", "")), [doc.page_content for doc in documents]


def answer_with_baseline(question: str, model: Any) -> str:
    """Run the same configured generation model without document retrieval."""
    answer = (BASELINE_PROMPT | model).invoke({"question": question})
    return str(getattr(answer, "content", answer))


def make_judge(model_name: str) -> Any:
    """Configure an independent OpenRouter model as the RAGAS judge."""
    api_key = os.getenv("OPENROUTER_JUDGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Set OPENROUTER_JUDGE_API_KEY in backend/.env. Use a key from the "
            "separate OpenRouter judge account."
        )
    try:
        from openai import OpenAI
        from ragas.cache import DiskCacheBackend
        from ragas.llms import llm_factory
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Install the evaluation group "
            "from backend/pyproject.toml."
        ) from exc

    cache_model = "".join(
        char if char.isalnum() else "_" for char in model_name.lower()
    ).strip("_")
    judge_cache = DiskCacheBackend(
        cache_dir=str(
            BACKEND_DIR / "evaluation" / f".ragas_judge_cache_openrouter_{cache_model}"
        )
    )
    judge = llm_factory(
        model_name,
        provider="openai",
        client=OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        ),
        cache=judge_cache,
    )
    return judge


def run_evaluation(dataset_rows: list[dict[str, str]], output_dir: Path) -> None:
    """Run both generation conditions and save per-question RAGAS scores."""
    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings

        # RAGAS 0.4.3 imports ChatVertexAI from a module path removed from
        # langchain-community 0.4.x. This evaluation uses Gemini AI Studio,
        # not Vertex AI, so provide a harmless type for RAGAS's optional
        # multi-completion detection when that legacy module is unavailable.
        try:
            from langchain_community.chat_models.vertexai import (  # noqa: F401
                ChatVertexAI,
            )
        except ModuleNotFoundError as exc:
            if exc.name != "langchain_community.chat_models.vertexai":
                raise
            import types

            vertexai_compat = types.ModuleType(
                "langchain_community.chat_models.vertexai"
            )
            vertexai_compat.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[vertexai_compat.__name__] = vertexai_compat

        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import (
            AnswerCorrectness,
            AnswerRelevancy,
            ContextRecall,
            Faithfulness,
        )
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Install the evaluation group "
            "from backend/pyproject.toml."
        ) from exc

    judge_name = os.getenv(
        "OPENROUTER_JUDGE_MODEL", "google/gemini-3.1-flash-lite"
    ).strip()
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
            AnswerRelevancy(
                llm=judge,
                embeddings=judge_embeddings,
                strictness=ANSWER_RELEVANCY_STRICTNESS,
            ),
            AnswerCorrectness(llm=judge, embeddings=judge_embeddings),
        ]

    rag_metrics = [
        Faithfulness(llm=judge),
        ContextRecall(llm=judge),
        *shared_metrics(),
    ]

    run_config = RunConfig(max_workers=1)
    rag_result = evaluate(
        Dataset.from_list(rag_rows),
        metrics=rag_metrics,
        run_config=run_config,
        raise_exceptions=True,
    )
    baseline_result = evaluate(
        Dataset.from_list(baseline_rows),
        metrics=shared_metrics(),
        run_config=run_config,
        raise_exceptions=True,
    )

    rag_frame = rag_result.to_pandas()
    rag_frame.insert(0, "system", "RAG")
    baseline_frame = baseline_result.to_pandas()
    baseline_frame.insert(0, "system", "Baseline")
    import pandas as pd

    report_metadata = [
        "case_id",
        "source_file",
        "source_url",
        "category",
        "answerability",
    ]
    for result_frame in (rag_frame, baseline_frame):
        if len(result_frame) != len(dataset_rows):
            raise RuntimeError(
                "RAGAS returned a different number of rows than the input dataset."
            )
        for column in report_metadata:
            result_frame[column] = [row[column] for row in dataset_rows]

    combined = pd.concat([rag_frame, baseline_frame], ignore_index=True, sort=False)
    combined["generation_model"] = get_model_name()
    combined["generation_provider"] = get_model_provider()
    combined["judge_model"] = judge_name
    combined["judge_provider"] = "openrouter"
    combined["answer_relevancy_strictness"] = ANSWER_RELEVANCY_STRICTNESS
    required_scores = {
        "RAG": [
            "faithfulness",
            "context_recall",
            "answer_relevancy",
            "answer_correctness",
        ],
        "Baseline": ["answer_relevancy", "answer_correctness"],
    }
    for system, columns in required_scores.items():
        system_scores = combined.loc[combined["system"] == system, columns]
        finite_scores = all(
            math.isfinite(float(value)) for value in system_scores.to_numpy().flat
        )
        if system_scores.isna().any().any() or not finite_scores:
            raise RuntimeError(
                f"{system} evaluation contains missing or invalid judge scores. "
                "No report was written; check the judge API response and billing."
            )
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
    print(f"Judge model: {judge_name} (OpenRouter)")
    print(
        "Answer relevancy strictness: "
        f"{ANSWER_RELEVANCY_STRICTNESS} generated sample per answer"
    )
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
