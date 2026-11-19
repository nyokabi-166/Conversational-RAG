"""Baseline repeatability: same 15 dev questions x 3 runs, no retrieval.

Mirrors analysis_extras/final/consistency_check.py (same questions, same model
settings) but calls the baseline path. Writes
analysis_extras/addendum/consistency_baseline.json after every call so it can
resume. Existing consistency.json is not touched. No secrets are printed.

Run from the repo root:
    backend\\.venv\\Scripts\\python.exe analysis_extras\\addendum\\baseline_repeat.py
"""
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = Path(__file__).resolve().parent / "consistency_baseline.json"
DEV_CSV = ROOT / "analysis_extras" / "round4" / "dev_questions.csv"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
os.chdir(BACKEND)
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from evaluate_rag import answer_with_baseline  # noqa: E402
from src.modules.llm import get_chat_model  # noqa: E402

IDS = ("D01", "D03", "D05", "D06", "D07", "D10", "D12", "D13", "D15",
       "D16", "D17", "D19", "D20", "D23", "D29")
RUNS = 3

with DEV_CSV.open(encoding="utf-8-sig", newline="") as handle:
    rows = {r["dev_id"]: r for r in csv.DictReader(handle)}

if OUT.is_file():
    payload = json.loads(OUT.read_text(encoding="utf-8"))
else:
    payload = {"runs_per_question": RUNS,
               "questions": [{"id": i, "question": rows[i]["question"], "answers": []} for i in IDS]}

model = get_chat_model()
for run in range(RUNS):
    for item in payload["questions"]:
        if len(item["answers"]) > run:
            continue
        item["answers"].append(answer_with_baseline(item["question"], model))
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Run {run + 1}/{RUNS} done", flush=True)
print("Done:", OUT)
