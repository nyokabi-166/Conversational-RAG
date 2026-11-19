"""Evaluate the RAG and no-retrieval baseline using the project's own backend."""

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from langchain_chroma import Chroma  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from src.modules.answer_quality import (  # noqa: E402
    detail_hints_enabled,
    guard_enabled,
)
from src.modules.prompts import BASELINE_SYSTEM_PROMPT
from src.modules.llm import (  # noqa: E402
    get_chat_model,
    get_llm_chain,
    get_llm_seed,
    get_llm_temperature,
    get_model_name,
    get_model_provider,
)
from src.modules.load_vesctorstore import PERSIST_DIR  # noqa: E402
from src.modules.query_handlers import (  # noqa: E402
    format_policy_context,
    get_retrieval_expansion_mode,
    query_chain,
    retrieve_policy_documents,
)
from src.rag_pipeline import MiniLMEmbeddings  # noqa: E402

CALL_TRACKER = {
    "rag_generation": 0,
    "baseline_generation": 0,
    "judge": 0,
    "total": 0,
}


def get_git_commit_hash() -> str:
    """Read the current git commit SHA in a read-only manner."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except Exception:
        return "unknown"


def get_git_dirty() -> bool | None:
    """Whether tracked files differ from HEAD; None when git is unavailable."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def _effective_settings() -> dict[str, Any]:
    """Settings that change generated answers or judge scores.

    Values are resolved through the application helpers, so an unset environment
    variable is recorded with the default it actually used instead of as "".
    """
    return {
        "temperature": get_llm_temperature(),
        "seed": get_llm_seed(),
        "generation_provider": get_model_provider(),
        "generation_model": get_model_name(),
        "retrieval_expansion": get_retrieval_expansion_mode(),
        "retrieval_limit": 8,
        "chunk_size": 1000,
        "chunk_overlap": 150,
        "answerability_guard": guard_enabled(),
        "detail_hints": detail_hints_enabled(),
        "answer_relevancy_strictness": ANSWER_RELEVANCY_STRICTNESS,
        "judge_max_tokens": int(
            os.getenv("RAGAS_JUDGE_MAX_TOKENS", str(DEFAULT_JUDGE_MAX_TOKENS))
        ),
    }


def write_run_metadata(
    output_dir: Path,
    dataset_path: Path,
    vectorstore: Chroma,
    judge_name: str,
    judge_provider: str,
) -> dict[str, Any]:
    """Write run_metadata.json at the start of an evaluation run."""
    from importlib.metadata import version as package_version

    modules_dir = BACKEND_DIR / "src" / "modules"
    script_path = Path(__file__).resolve()
    settings = _effective_settings()

    # Index chunk count and per-source counts
    collection_data = vectorstore._collection.get(include=["metadatas"])
    metadatas = collection_data.get("metadatas") or []
    chunk_count = len(metadatas)
    per_source: dict[str, int] = {}
    for meta in metadatas:
        if meta and "source" in meta:
            src = meta["source"]
            per_source[src] = per_source.get(src, 0) + 1

    metadata_path = output_dir / "run_metadata.json"
    previous: dict[str, Any] = {}
    try:
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    resuming = previous.get("status") == "running"
    if resuming:
        for key in ("rag_generation", "baseline_generation", "judge", "total"):
            CALL_TRACKER[key] += int(previous.get("call_counts", {}).get(key, 0))

    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "status": "running",
        "git_commit": get_git_commit_hash(),
        "git_dirty": get_git_dirty(),
        "source_sha256": {
            "prompts.py": _sha256_file(modules_dir / "prompts.py"),
            "llm.py": _sha256_file(modules_dir / "llm.py"),
            "query_handlers.py": _sha256_file(modules_dir / "query_handlers.py"),
            "answer_quality.py": _sha256_file(modules_dir / "answer_quality.py"),
            "corpus_vocabulary.json": _sha256_file(
                modules_dir / "corpus_vocabulary.json"
            ),
            "evaluate_rag.py": _sha256_file(script_path),
        },
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256_file(dataset_path),
        "index_chunk_count": chunk_count,
        "index_per_source_counts": dict(sorted(per_source.items())),
        "retrieval_mode": settings["retrieval_expansion"],
        "temperature": settings["temperature"],
        "seed": settings["seed"],
        "generation_model": settings["generation_model"],
        "generation_provider": settings["generation_provider"],
        "judge_model": judge_name,
        "judge_provider": judge_provider,
        "ragas_version": package_version("ragas"),
        "settings": settings,
        "start_time": previous.get("start_time", now) if resuming else now,
        "resumed_at": now if resuming else None,
        "end_time": None,
        "stage_counts": previous.get("stage_counts", {}) if resuming else {},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote run metadata to {metadata_path}")
    return metadata


def finalize_run_metadata(
    output_dir: Path, status: str, **updates: Any
) -> dict[str, Any]:
    """Close a run by recording its end time, status and stage counts."""
    metadata_path = output_dir / "run_metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    end = datetime.now(timezone.utc)
    metadata["status"] = status
    metadata["end_time"] = end.isoformat()
    try:
        started = datetime.fromisoformat(metadata["start_time"])
        metadata["duration_seconds"] = round((end - started).total_seconds(), 1)
    except (KeyError, TypeError, ValueError):
        metadata["duration_seconds"] = None
    metadata["call_counts"] = dict(CALL_TRACKER)
    metadata.update(updates)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _is_billing_error(exc: BaseException) -> bool:
    message = str(exc).casefold()
    status = getattr(exc, "status_code", None)
    return status == 402 or any(
        marker in message
        for marker in ("402", "spending limit", "insufficient balance", "payment required")
    )


def _raise_with_billing_context(
    exc: BaseException, output_dir: Path, checkpoint: Path | None
) -> None:
    finalize_run_metadata(output_dir, "failed", error=str(exc))
    if _is_billing_error(exc):
        print("\n" + "!" * 72)
        print("DeepInfra rejected the request: the API key has reached its spending limit.")
        print(f"Completed work is saved under: {output_dir / '.checkpoints'}")
        if checkpoint is not None:
            print(f"Latest checkpoint: {checkpoint}")
        print("Top up the account, then re-run the same command to resume.")
        print("!" * 72 + "\n")
    raise exc

DEFAULT_DATASET = BACKEND_DIR / "evaluation" / "dataset.csv"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "evaluation" / "results"
ANSWER_RELEVANCY_STRICTNESS = 1
EVALUATION_BATCH_SIZE = 1
DEFAULT_JUDGE_MAX_TOKENS = 4096
BASELINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", BASELINE_SYSTEM_PROMPT),
        ("human", "{question}"),
    ]
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a checkpoint atomically so an interrupted run remains resumable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(path)


def _generation_fingerprint(dataset_rows: list[dict[str, str]]) -> str:
    """Identify generated answers by input data, generation code and settings.

    Every file that can change an answer is hashed, including the packaged corpus
    vocabulary. Effective defaults are recorded as used, not as empty env vars.
    """
    modules_dir = BACKEND_DIR / "src" / "modules"
    source_files = (
        modules_dir / "llm.py",
        modules_dir / "query_handlers.py",
        modules_dir / "prompts.py",
        modules_dir / "answer_quality.py",
        modules_dir / "corpus_vocabulary.json",
    )
    source_hash = hashlib.sha256()
    for source_file in source_files:
        source_hash.update(source_file.read_bytes())

    configuration = {
        "fingerprint_version": 2,
        "dataset": dataset_rows,
        "generation_provider": get_model_provider(),
        "generation_model": get_model_name(),
        "source_hash": source_hash.hexdigest(),
        "settings": {
            key: value
            for key, value in _effective_settings().items()
            if key not in {"judge_max_tokens", "answer_relevancy_strictness"}
        },
    }
    serialized = json.dumps(configuration, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def _score_fingerprint(
    generation_fingerprint: str, judge_provider: str, judge_name: str
) -> str:
    """Identify judge scores by scoring code, metric settings and judge model."""
    from importlib.metadata import version as package_version

    evaluation_code_hash = hashlib.sha256(
        Path(__file__).resolve().read_bytes()
    ).hexdigest()
    configuration = {
        "fingerprint_version": 2,
        "generation_fingerprint": generation_fingerprint,
        "judge_provider": judge_provider,
        "judge_model": judge_name,
        "ragas_version": package_version("ragas"),
        "answer_relevancy_strictness": ANSWER_RELEVANCY_STRICTNESS,
        "evaluation_code_hash": evaluation_code_hash,
        "judge_max_tokens": int(
            os.getenv("RAGAS_JUDGE_MAX_TOKENS", str(DEFAULT_JUDGE_MAX_TOKENS))
        ),
    }
    serialized = json.dumps(configuration, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def _write_score_checkpoint(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    """Persist completed RAGAS rows after each small batch."""
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    pd.DataFrame(rows.values()).to_csv(temporary_path, index=False)
    temporary_path.replace(path)


def _score_in_batches(
    *,
    dataset_rows: list[dict[str, str]],
    score_rows: list[dict[str, Any]],
    system: str,
    metrics_factory: Any,
    evaluate: Any,
    Dataset: Any,
    run_config: Any,
    checkpoint_path: Path,
) -> Any:
    """Score cases in small resumable batches and return them in dataset order."""
    import pandas as pd

    completed: dict[str, dict[str, Any]] = {}
    if checkpoint_path.is_file():
        checkpoint_frame = pd.read_csv(checkpoint_path).fillna("")
        if "case_id" in checkpoint_frame.columns:
            completed = {
                str(row["case_id"]): row
                for row in checkpoint_frame.to_dict(orient="records")
            }

    pending = [row for row in dataset_rows if row["case_id"] not in completed]
    print(
        f"{system}: {len(completed)}/{len(dataset_rows)} cases already scored; "
        f"{len(pending)} remaining. Checkpoint: {checkpoint_path}"
    )

    for offset in range(0, len(pending), EVALUATION_BATCH_SIZE):
        batch = pending[offset : offset + EVALUATION_BATCH_SIZE]
        batch_ids = {row["case_id"] for row in batch}
        ragas_rows = [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row["ground_truth"],
            }
            for row in score_rows
            if row["case_id"] in batch_ids
        ]
        first_case = batch[0]["case_id"]
        last_case = batch[-1]["case_id"]
        print(f"Scoring {system} cases {first_case}–{last_case}")
        try:
            result = evaluate(
                Dataset.from_list(ragas_rows),
                metrics=metrics_factory(),
                run_config=run_config,
                raise_exceptions=True,
                batch_size=1,
            )
        except Exception as exc:
            raise RuntimeError(
                f"RAGAS judge failed while scoring {system} near {first_case}. "
                f"Completed scores are saved in {checkpoint_path}. After the "
                "judge limit or credit issue is resolved, rerun the same command "
                "to resume this evaluation."
            ) from exc

        result_frame = result.to_pandas()
        if len(result_frame) != len(batch):
            raise RuntimeError(
                f"RAGAS returned {len(result_frame)} rows for a batch of "
                f"{len(batch)} cases ({system})."
            )
        for case, (_, result_row) in zip(batch, result_frame.iterrows()):
            completed[case["case_id"]] = {
                "case_id": case["case_id"],
                "system": system,
                **result_row.to_dict(),
            }
        _write_score_checkpoint(checkpoint_path, completed)

    return pd.DataFrame([completed[row["case_id"]] for row in dataset_rows])


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


def get_judge_provider() -> str:
    """Return the RAGAS judge provider, defaulting to DeepInfra."""
    provider = os.getenv("RAGAS_JUDGE_PROVIDER", "deepinfra").strip().lower()
    if provider not in {"deepinfra", "openrouter"}:
        raise RuntimeError(
            "Unsupported RAGAS_JUDGE_PROVIDER. Choose 'deepinfra' or 'openrouter'."
        )
    return provider


def get_judge_model(provider: str) -> str:
    """Return the selected judge model ID."""
    if provider == "deepinfra":
        return (
            os.getenv("DEEPINFRA_JUDGE_MODEL", "google/gemini-3.1-flash-lite").strip()
            or "google/gemini-3.1-flash-lite"
        )
    return (
        os.getenv("OPENROUTER_JUDGE_MODEL", "google/gemini-3.1-flash-lite").strip()
        or "google/gemini-3.1-flash-lite"
    )


def make_judge(model_name: str, provider: str) -> Any:
    """Configure an independent RAGAS judge through an OpenAI-compatible API."""
    if provider == "deepinfra":
        api_key = (
            os.getenv("DEEPINFRA_JUDGE_API_KEY", "").strip()
            or os.getenv("DEEPINFRA_API_KEY", "").strip()
        )
        base_url = "https://api.deepinfra.com/v1/openai"
        key_hint = "DEEPINFRA_JUDGE_API_KEY or DEEPINFRA_API_KEY"
    else:
        api_key = os.getenv("OPENROUTER_JUDGE_API_KEY", "").strip()
        base_url = "https://openrouter.ai/api/v1"
        key_hint = "OPENROUTER_JUDGE_API_KEY"
    if not api_key:
        raise RuntimeError(
            f"Set {key_hint} in backend/.env to use {provider} for RAGAS judging."
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
            BACKEND_DIR / "evaluation" / f".ragas_judge_cache_{provider}_{cache_model}"
        )
    )
    raw_client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
        max_retries=1,
    )
    real_create = raw_client.chat.completions.create

    def tracking_create(*args, **kwargs):
        CALL_TRACKER["judge"] += 1
        CALL_TRACKER["total"] += 1
        return real_create(*args, **kwargs)

    raw_client.chat.completions.create = tracking_create

    judge = llm_factory(
        model_name,
        provider="openai",
        client=raw_client,
        cache=judge_cache,
        max_tokens=int(
            os.getenv("RAGAS_JUDGE_MAX_TOKENS", str(DEFAULT_JUDGE_MAX_TOKENS))
        ),
    )
    return judge


def run_evaluation(
    dataset_rows: list[dict[str, str]],
    output_dir: Path,
    dataset_path: Path = DEFAULT_DATASET,
    dry_run: bool = False,
) -> None:
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

    judge_provider = get_judge_provider()
    judge_name = get_judge_model(judge_provider)
    generation_fingerprint = _generation_fingerprint(dataset_rows)
    score_fingerprint = _score_fingerprint(
        generation_fingerprint, judge_provider, judge_name
    )
    generation_cache_dir = output_dir / ".checkpoints" / "generations"
    generation_cache_path = generation_cache_dir / f"{generation_fingerprint}.json"
    score_checkpoint_dir = output_dir / ".checkpoints" / "scores" / score_fingerprint

    vectorstore = load_vectorstore()
    write_run_metadata(output_dir, dataset_path, vectorstore, judge_name, judge_provider)

    generation_cache: dict[str, Any] = {
        "fingerprint": generation_fingerprint,
        "generation_provider": get_model_provider(),
        "generation_model": get_model_name(),
        "answers": {},
    }
    if generation_cache_path.is_file():
        try:
            cached_payload = json.loads(
                generation_cache_path.read_text(encoding="utf-8")
            )
            if (
                cached_payload.get("fingerprint") == generation_fingerprint
                and cached_payload.get("generation_provider") == get_model_provider()
                and cached_payload.get("generation_model") == get_model_name()
            ):
                generation_cache = cached_payload
        except (OSError, json.JSONDecodeError):
            print("Ignoring an unreadable answer checkpoint and starting a new one.")

    generated_answers = generation_cache.setdefault("answers", {})
    rag_chain = None
    baseline_model = None
    reused_answers = 0
    for index, row in enumerate(dataset_rows, start=1):
        question = row["question"]
        documents = retrieve_policy_documents(vectorstore, question)
        context = format_policy_context(documents)
        retrieved_contexts = [doc.page_content for doc in documents]
        saved = generated_answers.get(row["case_id"])

        if (
            saved
            and saved.get("question") == question
            and saved.get("contexts") == retrieved_contexts
            and saved.get("ground_truth") == row["ground_truth"]
        ):
            print(f"[{index}/{len(dataset_rows)}] Reusing saved answers")
            reused_answers += 1
            continue

        print(f"[{index}/{len(dataset_rows)}] Generating RAG and baseline answers")
        if rag_chain is None:
            rag_chain = get_llm_chain()
        if baseline_model is None:
            baseline_model = get_chat_model()
        try:
            rag_result = query_chain(
                rag_chain, question, context=context, source_docs=documents
            )
            if rag_result.get("error"):
                raise RuntimeError(f"RAG generation failed: {rag_result['error']}")
            if not rag_result.get("refused_by_guard"):
                CALL_TRACKER["rag_generation"] += 1
                CALL_TRACKER["total"] += 1
            rag_answer = str(rag_result.get("response", ""))
            baseline_answer = answer_with_baseline(question, baseline_model)
        except Exception as exc:
            _raise_with_billing_context(exc, output_dir, generation_cache_path)
        CALL_TRACKER["baseline_generation"] += 1
        CALL_TRACKER["total"] += 1
        generated_answers[row["case_id"]] = {
            "case_id": row["case_id"],
            "question": question,
            "ground_truth": row["ground_truth"],
            "rag_answer": rag_answer,
            "contexts": retrieved_contexts,
            "baseline_answer": baseline_answer,
        }
        _atomic_write_json(generation_cache_path, generation_cache)

    rag_rows = [
        {
            "case_id": row["case_id"],
            "question": row["question"],
            "answer": generated_answers[row["case_id"]]["rag_answer"],
            "contexts": generated_answers[row["case_id"]]["contexts"],
            "ground_truth": row["ground_truth"],
        }
        for row in dataset_rows
    ]
    baseline_rows = [
        {
            "case_id": row["case_id"],
            "question": row["question"],
            "answer": generated_answers[row["case_id"]]["baseline_answer"],
            # The baseline has no retrieved evidence by design.
            "contexts": [],
            "ground_truth": row["ground_truth"],
        }
        for row in dataset_rows
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    stage_counts = {
        "dataset_rows": len(dataset_rows),
        "reused_answers": reused_answers,
        "rag_generation_calls": CALL_TRACKER["rag_generation"],
        "baseline_generation_calls": CALL_TRACKER["baseline_generation"],
        "judge_calls": 0,
    }

    if dry_run:
        full_dataset_rows = len(read_dataset(dataset_path, None))
        per_question = CALL_TRACKER["total"] / len(dataset_rows) if dataset_rows else 0
        projected = round(per_question * full_dataset_rows)
        print("\n" + "=" * 60)
        print("DRY RUN SUMMARY (no judge calls)")
        print("-" * 60)
        print(f"Questions processed:        {len(dataset_rows)}")
        print(f"Generation calls used:      {CALL_TRACKER['total']}")
        print(f"Per-question average:       {per_question:.2f}")
        print(f"Full dataset ({full_dataset_rows} rows) generation projection: ~{projected}")
        print(
            "Judge projection:           "
            f">= {full_dataset_rows * 6} calls (6 metrics per row minimum)"
        )
        print(f"Answers were saved under:   {generation_cache_path}")
        print("=" * 60 + "\n")
        finalize_run_metadata(
            output_dir,
            "dry_run_complete",
            stage_counts={
                **stage_counts,
                "full_dataset_rows": full_dataset_rows,
                "projected_generation_calls": projected,
                "minimum_judge_calls": full_dataset_rows * 6,
            },
        )
        return

    judge = make_judge(judge_name, judge_provider)
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    def shared_metrics():
        return [
            AnswerRelevancy(
                llm=judge,
                embeddings=judge_embeddings,
                strictness=ANSWER_RELEVANCY_STRICTNESS,
            ),
            AnswerCorrectness(llm=judge, embeddings=judge_embeddings),
        ]

    def rag_metrics():
        return [
            Faithfulness(llm=judge),
            ContextRecall(llm=judge),
            *shared_metrics(),
        ]

    run_config = RunConfig(max_workers=1, max_retries=3, max_wait=60)
    try:
        rag_frame = _score_in_batches(
            dataset_rows=dataset_rows,
            score_rows=rag_rows,
            system="RAG",
            metrics_factory=rag_metrics,
            evaluate=evaluate,
            Dataset=Dataset,
            run_config=run_config,
            checkpoint_path=score_checkpoint_dir / "rag.csv",
        )
    except Exception as exc:
        _raise_with_billing_context(
            exc, output_dir, score_checkpoint_dir / "rag.csv"
        )
    try:
        baseline_frame = _score_in_batches(
            dataset_rows=dataset_rows,
            score_rows=baseline_rows,
            system="Baseline",
            metrics_factory=shared_metrics,
            evaluate=evaluate,
            Dataset=Dataset,
            run_config=run_config,
            checkpoint_path=score_checkpoint_dir / "baseline.csv",
        )
    except Exception as exc:
        _raise_with_billing_context(
            exc, output_dir, score_checkpoint_dir / "baseline.csv"
        )
    import pandas as pd

    report_metadata = [
        "case_id",
        "source_file",
        "source_url",
        "category",
        "answerability",
    ]
    metadata_by_case = {row["case_id"]: row for row in dataset_rows}
    for result_frame in (rag_frame, baseline_frame):
        if len(result_frame) != len(dataset_rows):
            raise RuntimeError(
                "RAGAS returned a different number of rows than the input dataset."
            )
        for column in report_metadata[1:]:
            result_frame[column] = [
                metadata_by_case[case_id][column] for case_id in result_frame["case_id"]
            ]

    combined = pd.concat([rag_frame, baseline_frame], ignore_index=True, sort=False)
    combined["generation_model"] = get_model_name()
    combined["generation_provider"] = get_model_provider()
    combined["judge_model"] = judge_name
    combined["judge_provider"] = judge_provider
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
    print(f"Judge model: {judge_name} ({judge_provider})")
    print(
        "Answer relevancy strictness: "
        f"{ANSWER_RELEVANCY_STRICTNESS} generated sample per answer"
    )
    print(combined.groupby("system")[summary_columns].mean(numeric_only=True))
    print(f"\nSaved per-question scores to {output_dir / 'evaluation_report.csv'}")

    print("\n" + "=" * 60)
    print("EVALUATION CALL COUNTS")
    print("-" * 60)
    print(f"RAG generation calls:      {CALL_TRACKER['rag_generation']}")
    print(f"Baseline generation calls: {CALL_TRACKER['baseline_generation']}")
    print(f"Judge API calls:           {CALL_TRACKER['judge']}")
    print(f"Total DeepInfra calls:     {CALL_TRACKER['total']}")
    print("=" * 60 + "\n")

    stage_counts["judge_calls"] = CALL_TRACKER["judge"]
    finalize_run_metadata(
        output_dir,
        "completed",
        stage_counts=stage_counts,
        report_path=str(output_dir / "evaluation_report.csv"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--limit", type=int, default=None, help="Run only the first N rows (demo mode)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process only the first 5 questions into a temporary results folder and print call counts.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    output_dir = args.output_dir
    limit = args.limit
    if args.dry_run:
        limit = 5
        if output_dir == DEFAULT_OUTPUT_DIR:
            output_dir = BACKEND_DIR / "evaluation" / "results_dry_run"
    try:
        run_evaluation(
            read_dataset(args.dataset, limit),
            output_dir,
            dataset_path=args.dataset,
            dry_run=args.dry_run,
        )
    except Exception:
        metadata_path = output_dir / "run_metadata.json"
        try:
            if json.loads(metadata_path.read_text(encoding="utf-8")).get(
                "status"
            ) == "running":
                finalize_run_metadata(output_dir, "failed")
        except (OSError, json.JSONDecodeError):
            pass
        raise


if __name__ == "__main__":
    main()
