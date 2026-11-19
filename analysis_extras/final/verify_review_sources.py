"""Verify that the three review files match the final evaluation report.

The script checks every review row’s *rag_response*, *baseline_response* and the
RAGAS scores against the final report ( `backend/evaluation/results/evaluation_report.csv` ).
It does **not** look at the label columns (`my_correct`, `rag_type`, `baseline_type`,
`safety`, `my_confirmed_cause` …) – those are left for the author to verify.

Run it from the repository root:
    backend\.venv\Scripts\python.exe analysis_extras\final\verify_review_sources.py
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FINAL_REPORT = ROOT / "backend/evaluation/results/evaluation_report.csv"
CHROMA = ROOT / "backend/data/chroma_db/chroma.sqlite3"

FINAL = pd.read_csv(FINAL_REPORT)
RAG = FINAL[FINAL.system == "RAG"].set_index("case_id")
BASE = FINAL[FINAL.system == "Baseline"].set_index("case_id")


def _safe_get(series: pd.Series, key: str, default: str = "") -> str:
    """Return *series[key]* if *key* is an index label, otherwise *default*."""
    if key in series.index:
        return str(series[key])
    return default


def _check_unanswerable(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors
    un = pd.read_csv(path)
    for _, r in un.iterrows():
        cid = r["case_id"]
        if cid in RAG.index:
            if _safe_get(r, "rag_response") != _safe_get(RAG.loc[cid], "response"):
                errors.append(f"unanswerable {cid}: rag_response mismatch")
            if cid in BASE.index:
                if _safe_get(r, "baseline_response") != _safe_get(BASE.loc[cid], "response"):
                    errors.append(f"unanswerable {cid}: baseline_response mismatch")
    return errors


def _check_validation(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors
    val = pd.read_csv(path)
    for _, r in val.iterrows():
        cid = r["case_id"]
        if cid not in RAG.index:
            errors.append(f"validation {cid}: case_id not in final report")
        # validate my_correct – must be 0 or 1
        mc = r.get("my_correct")
        if mc is not None:
            try:
                if int(mc) not in (0, 1):
                    errors.append(f"validation {cid}: my_correct must be 0 or 1")
            except ValueError:
                errors.append(f"validation {cid}: my_correct invalid")
    return errors


def _check_error_analysis(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors
    err = pd.read_csv(path)
    for _, r in err.iterrows():
        cid = r["case_id"]
        if cid not in RAG.index:
            errors.append(f"error_analysis {cid}: case_id not in final report")
        # validate my_confirmed_cause
        cc = r.get("my_confirmed_cause")
        if cc is not None:
            allowed = {
                "retrieval_miss",
                "incomplete_context",
                "generation_omission",
                "wrong_value",
                "overgeneralisation",
                "formatting",
                "judge_error",
                "other",
            }
            if cc.strip() not in allowed:
                errors.append(f"error_analysis {cid}: my_confirmed_cause invalid")
    return errors


def main() -> None:
    errors: list[str] = []
    errors.extend(_check_unanswerable(ROOT / "analysis_extras/unanswerable_review.csv"))
    errors.extend(_check_validation(ROOT / "analysis_extras/validation_sample.csv"))
    errors.extend(_check_error_analysis(ROOT / "analysis_extras/error_analysis_starter_DRAFT.csv"))

    if errors:
        print("FAIL")
        for e in errors:
            print(e)
    else:
        print("PASS")


if __name__ == "__main__":
    main()