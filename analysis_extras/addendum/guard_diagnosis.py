"""Check whether the answerability guard explains the paraphrase refusals.

Runs retrieval and the guard for the 45 pilot questions. No generation or judge
calls. Writes analysis_extras/addendum/guard_diagnosis.csv.
"""
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
os.chdir(BACKEND)
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")
from evaluate_rag import load_vectorstore
from src.modules.answer_quality import assess_context_coverage, question_terms
from src.modules.query_handlers import get_corpus_terms, retrieve_policy_documents

store = load_vectorstore()
terms_set = get_corpus_terms()
src = ROOT / "analysis_extras" / "addendum" / "paraphrase_dataset.csv"
out = ROOT / "analysis_extras" / "addendum" / "guard_diagnosis.csv"
rows = []
with src.open(encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        docs = retrieve_policy_documents(store, row["question"])
        cov = assess_context_coverage(
            row["question"], [d.page_content for d in docs], corpus_terms=terms_set
        )
        rows.append(
            {
                "case_id": row["case_id"],
                "question": row["question"],
                "refuse": cov["refuse"],
                "reason": cov["reason"],
                "missing_terms": "; ".join(cov["missing"]),
                "question_terms": "; ".join(question_terms(row["question"])),
            }
        )
with out.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print("done", sum(r["refuse"] for r in rows), "refused of", len(rows))
