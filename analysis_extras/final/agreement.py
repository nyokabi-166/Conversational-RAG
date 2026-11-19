"""Calculate agreement and Cohen's kappa between human labels and RAGAS scores.

Metrics computed:
1. Percent agreement and Cohen's kappa at thresholds 0.5 and 0.7
   between human labels ('my_correct') and RAGAS answer_correctness.
2. The same agreement on answerable questions only.
3. Label frequency counts for the unanswerable review sheet.
4. Confirmed error-cause counts for the optional error-analysis sheet.

Includes a built-in synthetic test mode:
    python analysis_extras/final/agreement.py --test-synthetic
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIDATION = ROOT / "analysis_extras" / "validation_sample.csv"
DEFAULT_UNANSWERABLE = ROOT / "analysis_extras" / "unanswerable_review.csv"
DEFAULT_ERROR = ROOT / "analysis_extras" / "error_analysis_starter_DRAFT.csv"
DEFAULT_DATASET = ROOT / "backend" / "evaluation" / "dataset.csv"
DEFAULT_OUT = ROOT / "analysis_extras" / "final"


def normalize_binary_label(val: Any) -> int | None:
    if pd.isna(val):
        return None
    text = str(val).strip().lower()
    if text in {"1", "1.0", "yes", "true", "y", "t", "correct"}:
        return 1
    if text in {"0", "0.0", "no", "false", "n", "f", "incorrect", "wrong"}:
        return 0
    return None


def compute_cohens_kappa(
    y_human: list[int], y_pred: list[int]
) -> dict[str, Any]:
    if len(y_human) != len(y_pred) or len(y_human) == 0:
        return {"n": 0, "percent_agreement": 0.0, "kappa": None}

    n = len(y_human)
    tp = sum(1 for h, p in zip(y_human, y_pred) if h == 1 and p == 1)
    tn = sum(1 for h, p in zip(y_human, y_pred) if h == 0 and p == 0)
    fp = sum(1 for h, p in zip(y_human, y_pred) if h == 0 and p == 1)
    fn = sum(1 for h, p in zip(y_human, y_pred) if h == 1 and p == 0)

    po = (tp + tn) / n
    p_human_1 = (tp + fn) / n
    p_human_0 = (tn + fp) / n
    p_pred_1 = (tp + fp) / n
    p_pred_0 = (tn + fn) / n
    pe = (p_human_1 * p_pred_1) + (p_human_0 * p_pred_0)
    kappa = (po - pe) / (1.0 - pe) if pe < 1.0 else None

    return {
        "n": n,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "percent_agreement": round(po * 100, 2),
        "pe": round(pe, 4),
        "kappa": round(kappa, 4) if kappa is not None else None,
    }


def load_validation(path: Path, dataset_path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["answerability"] = df["category"].map(
        lambda value: "unanswerable" if str(value).strip() == "unanswerable" else "answerable"
    )
    if dataset_path.is_file():
        dataset = pd.read_csv(dataset_path)
        if {"case_id", "answerability"}.issubset(dataset.columns):
            lookup = dataset.set_index("case_id")["answerability"]
            df["answerability"] = df["case_id"].map(lookup).fillna(df["answerability"])
    return df


def evaluate_subset(
    df: pd.DataFrame, thresholds: tuple[float, ...]
) -> dict[str, Any]:
    valid_rows: list[tuple[int, float]] = []
    for _, row in df.iterrows():
        label = normalize_binary_label(row.get("my_correct"))
        score = row.get("ragas_answer_correctness")
        if label is None or pd.isna(score):
            continue
        try:
            valid_rows.append((label, float(score)))
        except (TypeError, ValueError):
            continue

    result: dict[str, Any] = {
        "n_labeled": len(valid_rows),
        "total_rows": len(df),
        "thresholds": {},
    }
    if not valid_rows:
        result["message"] = "No valid human labels with RAGAS scores."
        return result

    y_human = [row[0] for row in valid_rows]
    scores = [row[1] for row in valid_rows]
    for threshold in thresholds:
        y_pred = [1 if score >= threshold else 0 for score in scores]
        result["thresholds"][str(threshold)] = compute_cohens_kappa(y_human, y_pred)
    return result


def evaluate_agreement(
    validation_csv: Path,
    dataset_csv: Path,
    thresholds: tuple[float, ...] = (0.5, 0.7),
) -> dict[str, Any]:
    if not validation_csv.is_file():
        return {"error": f"File not found: {validation_csv}"}

    df = load_validation(validation_csv, dataset_csv)
    result = evaluate_subset(df, thresholds)
    result["answerable_only"] = evaluate_subset(
        df[df["answerability"] == "answerable"], thresholds
    )
    result["unanswerable_only"] = evaluate_subset(
        df[df["answerability"] == "unanswerable"], thresholds
    )
    return result


def summarize_values(path: Path, columns: tuple[str, ...]) -> dict[str, Any]:
    if not path.is_file():
        return {"error": f"File not found: {path}"}

    df = pd.read_csv(path)
    summary: dict[str, Any] = {"total_rows": len(df)}
    for column in columns:
        if column in df.columns:
            counts = (
                df[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", "(empty)")
                .value_counts()
                .to_dict()
            )
            summary[column] = counts
        else:
            summary[column] = {}
    return summary


def summarize_unanswerable_review(path: Path) -> dict[str, Any]:
    return summarize_values(path, ("rag_type", "baseline_type", "safety"))


def summarize_error_causes(path: Path) -> dict[str, Any]:
    summary = summarize_values(path, ("my_confirmed_cause",))
    counts = summary.get("my_confirmed_cause", {})
    labeled = sum(
        count for value, count in counts.items() if value != "(empty)"
    )
    summary["labeled_rows"] = labeled
    summary["percentages"] = {
        value: round(count / labeled * 100, 2)
        for value, count in counts.items()
        if value != "(empty)" and labeled
    }
    return summary


def agreement_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    validation = report.get("validation_agreement", {})
    for subset in ("overall", "answerable_only", "unanswerable_only"):
        block = validation if subset == "overall" else validation.get(subset, {})
        for threshold, values in (block.get("thresholds") or {}).items():
            rows.append(
                {
                    "subset": subset,
                    "n": values.get("n"),
                    "threshold": threshold,
                    "percent_agreement": values.get("percent_agreement"),
                    "kappa": values.get("kappa"),
                    "tp": values.get("tp"),
                    "tn": values.get("tn"),
                    "fp": values.get("fp"),
                    "fn": values.get("fn"),
                }
            )
    return rows


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agreement_results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    pd.DataFrame(agreement_rows(report)).to_csv(
        out_dir / "agreement_summary.csv", index=False
    )

    unanswerable = report.get("unanswerable_summary", {})
    unanswerable_rows = []
    for column in ("rag_type", "baseline_type", "safety"):
        for value, count in (unanswerable.get(column) or {}).items():
            unanswerable_rows.append(
                {"column": column, "value": value, "count": count}
            )
    pd.DataFrame(unanswerable_rows).to_csv(
        out_dir / "unanswerable_summary.csv", index=False
    )

    error = report.get("error_cause_summary", {})
    counts = error.get("my_confirmed_cause") or {}
    error_rows = [
        {
            "cause": cause,
            "count": count,
            "percent": (error.get("percentages") or {}).get(cause),
        }
        for cause, count in counts.items()
        if cause != "(empty)"
    ]
    pd.DataFrame(error_rows).to_csv(
        out_dir / "error_cause_summary.csv", index=False
    )


def run_synthetic_test() -> dict[str, Any]:
    print("Running synthetic test of agreement and Cohen's kappa...")
    rng = np.random.default_rng(42)
    human = [1] * 35 + [0] * 15
    scores = [
        float(rng.uniform(0.6, 0.95)) if value == 1 else float(rng.uniform(0.05, 0.45))
        for value in human
    ]
    for index in (2, 7, 36, 40):
        scores[index] = 1.0 - scores[index]

    k_05 = compute_cohens_kappa(
        human, [1 if score >= 0.5 else 0 for score in scores]
    )
    k_07 = compute_cohens_kappa(
        human, [1 if score >= 0.7 else 0 for score in scores]
    )

    assert k_05["n"] == 50
    assert k_05["percent_agreement"] >= 80.0
    assert k_05["kappa"] > 0.6

    synthetic_un = pd.DataFrame(
        {
            "case_id": [f"U{i:02d}" for i in range(6)],
            "rag_type": ["refused", "refused", "refused", "refused", "partial_refusal", "refused"],
            "baseline_type": ["hallucinated", "hallucinated", "refused", "hallucinated", "hallucinated", "hallucinated"],
            "safety": ["safe", "safe", "safe", "safe", "safe", "safe"],
        }
    )
    test_results = {
        "status": "PASS",
        "threshold_0.5": k_05,
        "threshold_0.7": k_07,
        "synthetic_unanswerable_counts": {
            "rag_type": synthetic_un["rag_type"].value_counts().to_dict(),
            "baseline_type": synthetic_un["baseline_type"].value_counts().to_dict(),
            "safety": synthetic_un["safety"].value_counts().to_dict(),
        },
    }
    print(json.dumps(test_results, indent=2))
    return test_results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-csv", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--unanswerable-csv", type=Path, default=DEFAULT_UNANSWERABLE)
    parser.add_argument("--error-csv", type=Path, default=DEFAULT_ERROR)
    parser.add_argument("--dataset-csv", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--test-synthetic", action="store_true")
    args = parser.parse_args()

    if args.test_synthetic:
        run_synthetic_test()
        return

    report = {
        "validation_agreement": evaluate_agreement(
            args.validation_csv, args.dataset_csv
        ),
        "unanswerable_summary": summarize_unanswerable_review(
            args.unanswerable_csv
        ),
        "error_cause_summary": summarize_error_causes(args.error_csv),
    }
    write_outputs(report, args.out_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
