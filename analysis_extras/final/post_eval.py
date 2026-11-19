"""Offline post-processing for the final RAG evaluation.

Reads the per-question evaluation report produced by backend/scripts/evaluate_rag.py
and writes thesis-ready tables. It never changes the evaluation results.

Usage (from the repository root):
    backend\\.venv\\Scripts\\python.exe analysis_extras\\final\\post_eval.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = ROOT / "backend" / "evaluation" / "results"
DEFAULT_OUT = ROOT / "analysis_extras" / "final"

METRICS = ["faithfulness", "context_recall", "answer_relevancy", "answer_correctness"]
SHARED_METRICS = ["answer_relevancy", "answer_correctness"]
REFUSAL_RE = re.compile(
    r"couldn'?t find that in the kenya airways pages|could not find that in the kenya airways pages"
    r"|don'?t have (?:that|this|enough) information|do not have (?:that|this|enough) information"
    r"|unable to (?:provide|answer)|no information (?:about|on)",
    re.IGNORECASE,
)


def refused(answer: object) -> bool:
    return bool(REFUSAL_RE.search(str(answer or "")))


def bootstrap_ci(values: np.ndarray, samples: int = 10000) -> tuple[float, float]:
    rng = np.random.default_rng(42)
    draws = rng.integers(0, len(values), size=(samples, len(values)))
    means = values[draws].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_tests(rag: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    merged = rag.merge(baseline, on="case_id", suffixes=("_rag", "_baseline"))
    rows = []
    for metric in SHARED_METRICS:
        differences = (
            merged[f"{metric}_rag"].astype(float)
            - merged[f"{metric}_baseline"].astype(float)
        ).to_numpy()
        low, high = bootstrap_ci(differences)
        row = {
            "metric": metric,
            "n_pairs": len(differences),
            "rag_mean": round(float(merged[f"{metric}_rag"].mean()), 4),
            "baseline_mean": round(float(merged[f"{metric}_baseline"].mean()), 4),
            "mean_difference": round(float(differences.mean()), 4),
            "bootstrap_95_low": round(low, 4),
            "bootstrap_95_high": round(high, 4),
            "paired_t_p": None,
            "wilcoxon_p": None,
        }
        if len(differences) >= 2:
            row["paired_t_p"] = round(float(stats.ttest_rel(
                merged[f"{metric}_rag"], merged[f"{metric}_baseline"]
            ).pvalue), 6)
        if len(differences) >= 10 and np.any(differences != 0):
            row["wilcoxon_p"] = round(
                float(stats.wilcoxon(differences).pvalue), 6
            )
        rows.append(row)
    return pd.DataFrame(rows)


def metric_table(frame: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    available = [metric for metric in METRICS if metric in frame.columns]
    keys = list(dict.fromkeys(group + ["system"]))
    table = (
        frame.groupby(keys, dropna=False)[available]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    table.columns = [
        "_".join(str(part) for part in column if part).rstrip("_")
        if isinstance(column, tuple)
        else column
        for column in table.columns
    ]
    return table.round(4)


def refusal_table(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["refused"] = frame["response"].map(refused)
    grouped = (
        frame.groupby(["system", "answerability"], dropna=False)["refused"]
        .agg(["sum", "count"])
        .reset_index()
    )
    grouped["rate"] = (grouped["sum"] / grouped["count"]).round(3)
    grouped = grouped.rename(columns={"sum": "refused", "count": "questions"})
    return grouped


def consistency_table(path: Path) -> pd.DataFrame | None:
    """Summarize repeated runs when a consistency JSON file is supplied.

    Expected shape: {"questions": [{"id": ..., "question": ..., "answers": [...]}]}
    """
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("questions", []):
        answers = [" ".join(str(a).split()).casefold() for a in item.get("answers", [])]
        if len(answers) < 2:
            continue
        identical = len(set(answers)) == 1
        rows.append(
            {
                "id": item.get("id"),
                "runs": len(answers),
                "identical": int(identical),
                "refused": int(any(refused(a) for a in answers)),
            }
        )
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    return pd.DataFrame(
        [
            {
                "questions": len(frame),
                "runs_per_question": int(frame["runs"].max()),
                "identical_rate": round(float(frame["identical"].mean()), 3),
                "any_refusal_rate": round(float(frame["refused"].mean()), 3),
            }
        ]
    )


def markdown_summary(
    overall: pd.DataFrame,
    paired: pd.DataFrame,
    category: pd.DataFrame,
    refusals: pd.DataFrame,
    consistency: pd.DataFrame | None,
) -> str:
    lines = ["# Final evaluation summary", ""]

    lines += [
        "## Overall RAGAS scores",
        "",
        "| System | Metric | Mean | SD | n |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in overall.iterrows():
        for metric in METRICS:
            mean_col, sd_col, n_col = f"{metric}_mean", f"{metric}_std", f"{metric}_count"
            if mean_col not in overall.columns or pd.isna(row.get(mean_col)):
                continue
            lines.append(
                f"| {row['system']} | {metric} | {row[mean_col]:.3f} | "
                f"{row.get(sd_col, float('nan')):.3f} | {int(row[n_col])} |"
            )

    lines += [
        "",
        "## Paired RAG vs baseline",
        "",
        "| Metric | n | RAG | Baseline | Difference | 95% CI | t p | Wilcoxon p |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    for _, row in paired.iterrows():
        lines.append(
            f"| {row['metric']} | {row['n_pairs']} | {row['rag_mean']:.3f} | "
            f"{row['baseline_mean']:.3f} | {row['mean_difference']:+.3f} | "
            f"[{row['bootstrap_95_low']:+.3f}, {row['bootstrap_95_high']:+.3f}] | "
            f"{row['paired_t_p']} | {row['wilcoxon_p']} |"
        )

    lines += [
        "",
        "## Refusal rates",
        "",
        "| System | Answerability | Refused | Questions | Rate |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in refusals.iterrows():
        lines.append(
            f"| {row['system']} | {row['answerability']} | {row['refused']} | "
            f"{row['questions']} | {row['rate']:.1%} |"
        )

    if consistency is not None:
        row = consistency.iloc[0]
        lines += [
            "",
            "## Consistency check",
            "",
            f"- Questions: {int(row['questions'])}",
            f"- Runs per question: {int(row['runs_per_question'])}",
            f"- Identical answers: {row['identical_rate']:.1%}",
            f"- Questions with any refusal: {row['any_refusal_rate']:.1%}",
        ]

    lines += [
        "",
        "## Category breakdown",
        "",
        "See `category_metrics.csv` and `answerability_metrics.csv` for the full tables.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--consistency", type=Path, default=None)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    report_path = args.results_dir / "evaluation_report.csv"
    frame = pd.read_csv(report_path).fillna({"response": ""})
    for metric in METRICS:
        if metric in frame.columns:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")

    systems = set(frame["system"].unique())
    if {"RAG", "Baseline"} - systems:
        raise SystemExit(f"Expected RAG and Baseline rows, found {sorted(systems)}")
    counts = frame.groupby("system")["case_id"].nunique()
    if counts.nunique() != 1 and not args.allow_incomplete:
        raise SystemExit(f"System row counts differ: {counts.to_dict()}")

    rag = frame[frame["system"] == "RAG"]
    baseline = frame[frame["system"] == "Baseline"]

    overall = metric_table(frame, ["system"])
    paired = paired_tests(rag, baseline)
    category = metric_table(frame, ["category"])
    answerability = metric_table(frame, ["answerability"])
    refusals = refusal_table(frame)
    consistency = consistency_table(args.consistency) if args.consistency else None

    args.out_dir.mkdir(parents=True, exist_ok=True)
    overall.to_csv(args.out_dir / "overall_metrics.csv", index=False)
    paired.to_csv(args.out_dir / "paired_tests.csv", index=False)
    category.to_csv(args.out_dir / "category_metrics.csv", index=False)
    answerability.to_csv(args.out_dir / "answerability_metrics.csv", index=False)
    refusals.to_csv(args.out_dir / "refusal_summary.csv", index=False)
    if consistency is not None:
        consistency.to_csv(args.out_dir / "consistency_summary.csv", index=False)

    report = markdown_summary(overall, paired, category, refusals, consistency)
    (args.out_dir / "tables.md").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
