"""Run the final-build consistency check: 15 dev questions x 3 runs.

Writes analysis_extras/final/consistency.json after every run, so an interrupted
check can resume. No secrets are printed. The call budget is 45 generation calls
(guard refusals save a call).

Usage (from the repository root, after credits are topped up):
    backend\\.venv\\Scripts\\python.exe analysis_extras\\final\\consistency_check.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "analysis_extras" / "final"
DEV_CSV = ROOT / "analysis_extras" / "round4" / "dev_questions.csv"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from langchain_chroma import Chroma  # noqa: E402

from src.modules.llm import get_llm_chain  # noqa: E402
from src.modules.query_handlers import (  # noqa: E402
    format_policy_context,
    query_chain,
    retrieve_policy_documents,
)
from src.rag_pipeline import MiniLMEmbeddings  # noqa: E402

QUESTION_IDS = (
    "D01",
    "D03",
    "D05",
    "D06",
    "D07",
    "D10",
    "D12",
    "D13",
    "D15",
    "D16",
    "D17",
    "D19",
    "D20",
    "D23",
    "D29",
)
RUNS = 3
CALLS = {"generation": 0, "refused": 0}


def load_questions() -> list[dict[str, str]]:
    with DEV_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = {row["dev_id"]: row for row in csv.DictReader(handle)}
    missing = [qid for qid in QUESTION_IDS if qid not in rows]
    if missing:
        raise SystemExit(f"Missing dev questions: {missing}")
    return [rows[qid] for qid in QUESTION_IDS]


def load_checkpoint() -> dict:
    path = OUT / "consistency.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "runs_per_question": RUNS,
        "questions": [
            {"id": row["dev_id"], "question": row["question"], "answers": []}
            for row in load_questions()
        ],
    }


def save_checkpoint(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "consistency.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--max-calls", type=int, default=60)
    args = parser.parse_args()

    questions = load_questions()
    payload = load_checkpoint()
    if len(payload["questions"]) != len(questions):
        raise SystemExit("Checkpoint does not match the selected dev questions.")

    vectorstore = Chroma(
        persist_directory=str(BACKEND / "data" / "chroma_db"),
        embedding_function=MiniLMEmbeddings(),
    )
    chain = get_llm_chain()

    for run_index in range(args.runs):
        print(f"Run {run_index + 1}/{args.runs}", flush=True)
        for item in payload["questions"]:
            if len(item["answers"]) > run_index:
                continue
            if CALLS["generation"] >= args.max_calls:
                raise SystemExit(
                    f"Call budget reached ({args.max_calls}); rerun to resume."
                )
            documents = retrieve_policy_documents(vectorstore, item["question"])
            context = format_policy_context(documents)
            result = query_chain(
                chain, item["question"], context=context, source_docs=documents
            )
            if result.get("error"):
                raise SystemExit(f"Generation failed for {item['id']}: {result['error']}")
            if result.get("refused_by_guard"):
                CALLS["refused"] += 1
            else:
                CALLS["generation"] += 1
            item["answers"].append(str(result.get("response", "")))
            save_checkpoint(payload)
        save_checkpoint(payload)
        print(
            f"  saved; generation calls {CALLS['generation']}, "
            f"guard refusals {CALLS['refused']}",
            flush=True,
        )

    print(f"Done: {OUT / 'consistency.json'}")


if __name__ == "__main__":
    main()
