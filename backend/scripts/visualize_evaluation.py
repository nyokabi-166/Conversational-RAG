"""Create study figures and summaries from a completed RAGAS evaluation.

Run from the repository root:
    poetry -C backend run python scripts/visualize_evaluation.py

The SVG figures remain sharp in Word and the CSV files retain the underlying
summary values. Bootstrap intervals describe question-level variability for
this reviewed dataset; they are not by themselves a significance test.
"""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = BACKEND_DIR / "evaluation" / "results" / "evaluation_report.csv"
DEFAULT_DATASET = BACKEND_DIR / "evaluation" / "dataset.csv"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "evaluation" / "results"
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 169532
MIN_CATEGORY_N = 5
COLORS = {"RAG": "#2878B5", "Baseline": "#9AA6B2"}
METRICS_BY_SYSTEM = {
    "RAG": [
        "faithfulness",
        "context_recall",
        "answer_relevancy",
        "answer_correctness",
    ],
    "Baseline": ["answer_relevancy", "answer_correctness"],
}
COMPARISON_METRICS = ["answer_correctness", "answer_relevancy"]


def bootstrap_mean_interval(values: np.ndarray, seed: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        raise ValueError("Cannot calculate a confidence interval without scores.")
    if len(values) == 1:
        return float(values[0]), float(values[0])
    generator = np.random.default_rng(seed)
    indices = generator.integers(
        0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values))
    )
    bootstrap_means = values[indices].mean(axis=1)
    low, high = np.quantile(bootstrap_means, [0.025, 0.975])
    return float(low), float(high)


def attach_dataset_metadata(frame: pd.DataFrame, dataset_path: Path) -> pd.DataFrame:
    metadata = pd.read_csv(dataset_path)
    required = {"question", "case_id", "category"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(
            "Dataset is missing metadata columns needed for study figures: "
            + ", ".join(sorted(missing))
        )

    metadata = metadata.copy()
    metadata["_question_occurrence"] = metadata.groupby("question").cumcount()
    frame = frame.copy()
    frame["_question_occurrence"] = frame.groupby(["system", "question"]).cumcount()
    merge_columns = ["question", "_question_occurrence"]
    metadata_columns = [
        column
        for column in (
            "case_id",
            "source_file",
            "source_url",
            "category",
            "answerability",
        )
        if column in metadata.columns
    ]
    frame = frame.merge(
        metadata[merge_columns + metadata_columns],
        on=merge_columns,
        how="left",
        validate="many_to_one",
        suffixes=("", "_dataset"),
    )
    for column in metadata_columns:
        dataset_column = f"{column}_dataset"
        if dataset_column in frame.columns:
            if column in frame.columns:
                frame[column] = frame[column].where(
                    frame[column].notna() & (frame[column].astype(str) != ""),
                    frame[dataset_column],
                )
            else:
                frame[column] = frame[dataset_column]
            frame.drop(columns=[dataset_column], inplace=True)
    frame.drop(columns=["_question_occurrence"], inplace=True)
    if frame["case_id"].isna().any() or frame["category"].isna().any():
        raise ValueError(
            "Some report questions did not match the reviewed dataset. "
            "Check that the evaluation report and dataset are from the same run."
        )
    return frame


def read_scores(report_path: Path, dataset_path: Path) -> pd.DataFrame:
    if not report_path.is_file():
        raise FileNotFoundError(f"Evaluation report not found: {report_path}")
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Reviewed evaluation dataset not found: {dataset_path}"
        )

    frame = pd.read_csv(report_path)
    if "question" not in frame.columns and "user_input" in frame.columns:
        frame = frame.rename(columns={"user_input": "question"})
    required_columns = {"system", "question", *METRICS_BY_SYSTEM["RAG"]}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(
            "Report is missing required columns: " + ", ".join(sorted(missing_columns))
        )
    systems = set(frame["system"].dropna().unique())
    if not {"RAG", "Baseline"}.issubset(systems):
        raise ValueError("Report must contain both RAG and Baseline results.")

    for system, metrics in METRICS_BY_SYSTEM.items():
        subset = frame.loc[frame["system"] == system, metrics]
        numeric = subset.apply(pd.to_numeric, errors="coerce")
        if numeric.empty or numeric.isna().any().any():
            raise ValueError(
                f"{system} results contain missing or non-numeric required scores. "
                "Run a complete evaluation before making study figures."
            )
        values = numeric.to_numpy().flat
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError(f"{system} results contain invalid numeric scores.")
        if ((numeric < 0) | (numeric > 1)).any().any():
            raise ValueError(
                f"{system} scores must be between 0 and 1; check the report scale."
            )
        frame.loc[frame["system"] == system, metrics] = numeric

    frame = attach_dataset_metadata(frame, dataset_path)
    return frame


def metric_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seed = BOOTSTRAP_SEED
    for system, metrics in METRICS_BY_SYSTEM.items():
        subset = frame.loc[frame["system"] == system]
        for metric in metrics:
            values = pd.to_numeric(subset[metric]).to_numpy(dtype=float)
            ci_low, ci_high = bootstrap_mean_interval(values, seed)
            rows.append(
                {
                    "system": system,
                    "metric": metric,
                    "mean": values.mean(),
                    "standard_deviation": (
                        values.std(ddof=1) if len(values) > 1 else 0.0
                    ),
                    "ci_95_low": ci_low,
                    "ci_95_high": ci_high,
                    "n": len(values),
                }
            )
            seed += 1
    return pd.DataFrame(rows)


def paired_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for index, metric in enumerate(COMPARISON_METRICS):
        paired = frame.pivot(index="case_id", columns="system", values=metric)
        if paired[["RAG", "Baseline"]].isna().any().any():
            raise ValueError(f"Unpaired {metric} scores; each case needs both systems.")
        differences = paired["RAG"].to_numpy(dtype=float) - paired["Baseline"].to_numpy(
            dtype=float
        )
        ci_low, ci_high = bootstrap_mean_interval(
            differences, BOOTSTRAP_SEED + 100 + index
        )
        rows.append(
            {
                "metric": metric,
                "rag_mean": paired["RAG"].mean(),
                "baseline_mean": paired["Baseline"].mean(),
                "mean_paired_difference": differences.mean(),
                "ci_95_low": ci_low,
                "ci_95_high": ci_high,
                "n_paired_questions": len(differences),
            }
        )
    return pd.DataFrame(rows)


def category_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seed = BOOTSTRAP_SEED + 1000
    for category, group in frame.groupby("category", sort=False):
        for system in ("RAG", "Baseline"):
            values = pd.to_numeric(
                group.loc[group["system"] == system, "answer_correctness"]
            ).to_numpy(dtype=float)
            if not len(values):
                continue
            ci_low, ci_high = bootstrap_mean_interval(values, seed)
            rows.append(
                {
                    "category": category,
                    "system": system,
                    "mean_answer_correctness": values.mean(),
                    "ci_95_low": ci_low,
                    "ci_95_high": ci_high,
                    "n": len(values),
                    "included_in_figure": len(values) >= MIN_CATEGORY_N,
                }
            )
            seed += 1
    return pd.DataFrame(rows)


def svg_text(
    x: float, y: float, value: object, css: str = "label", anchor: str = "start"
) -> str:
    safe_value = html.escape(str(value), quote=False)
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" '
        f'text-anchor="{anchor}">{safe_value}</text>'
    )


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#17212b}"
        ".title{font-size:24px;font-weight:700}.subtitle{font-size:14px;fill:#56616c}"
        ".label{font-size:15px}.small{font-size:12px;fill:#56616c}"
        ".value{font-size:13px;font-weight:600}</style>",
        svg_text(24, 36, title, "title"),
        svg_text(24, 61, subtitle, "subtitle"),
    ]


def make_paired_difference_chart(summary: pd.DataFrame, output_path: Path) -> None:
    width, height = 1050, 340
    left, plot_width, top = 330, 420, 130
    parts = svg_start(
        width,
        height,
        "RAG compared with the no-retrieval baseline",
        "Paired mean difference (RAG − baseline), with 95% question-level bootstrap intervals.",
    )
    x_zero = left + plot_width / 2
    parts.append(
        f'<line x1="{x_zero:.1f}" y1="100" x2="{x_zero:.1f}" y2="270" '
        'stroke="#17212b" stroke-width="1.5" stroke-dasharray="5,5"/>'
    )
    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        x = left + ((tick + 1) / 2) * plot_width
        parts.append(
            f'<line x1="{x:.1f}" y1="270" x2="{x:.1f}" y2="276" ' 'stroke="#56616c"/>'
        )
        parts.append(svg_text(x, 296, f"{tick:+.1f}", "small", "middle"))

    for index, row in summary.iterrows():
        y = top + index * 78
        metric_label = str(row["metric"]).replace("_", " ").title()
        mean = float(row["mean_paired_difference"])
        low, high = float(row["ci_95_low"]), float(row["ci_95_high"])
        x_mean = left + ((mean + 1) / 2) * plot_width
        x_low = left + ((low + 1) / 2) * plot_width
        x_high = left + ((high + 1) / 2) * plot_width
        parts.append(svg_text(24, y + 5, metric_label))
        parts.append(
            f'<line x1="{x_low:.1f}" y1="{y}" x2="{x_high:.1f}" y2="{y}" '
            'stroke="#2878B5" stroke-width="4" stroke-linecap="round"/>'
        )
        parts.append(
            f'<line x1="{x_low:.1f}" y1="{y - 8}" x2="{x_low:.1f}" y2="{y + 8}" '
            'stroke="#2878B5" stroke-width="2"/>'
        )
        parts.append(
            f'<line x1="{x_high:.1f}" y1="{y - 8}" x2="{x_high:.1f}" y2="{y + 8}" '
            'stroke="#2878B5" stroke-width="2"/>'
        )
        parts.append(f'<circle cx="{x_mean:.1f}" cy="{y}" r="7" fill="#2878B5"/>')
        parts.append(
            svg_text(
                left + plot_width + 20,
                y + 5,
                f"Δ {mean:+.3f} [{low:+.3f}, {high:+.3f}] (n={int(row['n_paired_questions'])})",
                "value",
            )
        )

    parts.append(
        svg_text(
            left + plot_width / 2,
            324,
            "Mean paired score difference",
            "small",
            "middle",
        )
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def make_evidence_distribution_chart(
    frame: pd.DataFrame, summary: pd.DataFrame, output_path: Path
) -> None:
    width, height = 1040, 350
    left, plot_width, top = 260, 570, 145
    metrics = ["faithfulness", "context_recall"]
    parts = svg_start(
        width,
        height,
        "Evidence use in the RAG system",
        "Box shows the score distribution; diamond and interval show the mean and 95% bootstrap interval.",
    )
    for tick in range(0, 11, 2):
        x = left + plot_width * tick / 10
        parts.append(
            f'<line x1="{x:.1f}" y1="110" x2="{x:.1f}" y2="285" '
            'stroke="#e3e8ed" stroke-width="1"/>'
        )
        parts.append(svg_text(x, 307, f"{tick / 10:.1f}", "small", "middle"))

    for index, metric in enumerate(metrics):
        values = frame.loc[frame["system"] == "RAG", metric].to_numpy(dtype=float)
        y = top + index * 82
        low_whisker, q1, median, q3, high_whisker = np.quantile(
            values, [0.0, 0.25, 0.5, 0.75, 1.0]
        )
        row = summary.loc[
            (summary["system"] == "RAG") & (summary["metric"] == metric)
        ].iloc[0]
        mean = float(row["mean"])
        ci_low, ci_high = float(row["ci_95_low"]), float(row["ci_95_high"])
        scale = lambda score: left + plot_width * float(score)
        parts.append(svg_text(24, y + 5, metric.replace("_", " ").title()))
        parts.append(
            f'<line x1="{scale(low_whisker):.1f}" y1="{y}" '
            f'x2="{scale(high_whisker):.1f}" y2="{y}" stroke="#56616c" stroke-width="2"/>'
        )
        for whisker in (low_whisker, high_whisker):
            x = scale(whisker)
            parts.append(
                f'<line x1="{x:.1f}" y1="{y - 9}" x2="{x:.1f}" y2="{y + 9}" '
                'stroke="#56616c" stroke-width="2"/>'
            )
        parts.append(
            f'<rect x="{scale(q1):.1f}" y="{y - 15}" '
            f'width="{max(1.0, scale(q3) - scale(q1)):.1f}" height="30" '
            'fill="#d9e9f5" stroke="#2878B5" stroke-width="2"/>'
        )
        parts.append(
            f'<line x1="{scale(median):.1f}" y1="{y - 15}" '
            f'x2="{scale(median):.1f}" y2="{y + 15}" stroke="#17212b" stroke-width="2"/>'
        )
        parts.append(
            f'<line x1="{scale(ci_low):.1f}" y1="{y + 24}" '
            f'x2="{scale(ci_high):.1f}" y2="{y + 24}" stroke="#c4553d" stroke-width="3"/>'
        )
        parts.append(
            f'<path d="M {scale(mean):.1f} {y + 17} l 7 7 l -7 7 l -7 -7 z" '
            'fill="#c4553d"/>'
        )
        parts.append(
            svg_text(
                left + plot_width + 18,
                y + 5,
                f"mean {mean:.3f}; n={len(values)}",
                "value",
            )
        )
    parts.append(
        svg_text(left + plot_width / 2, 337, "RAGAS score (0–1)", "small", "middle")
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def make_category_chart(
    summary: pd.DataFrame, output_path: Path, min_n: int = MIN_CATEGORY_N
) -> None:
    included_categories = (
        summary.loc[summary["included_in_figure"]]
        .groupby("category")["n"]
        .max()
        .sort_values(ascending=False)
        .index.tolist()
    )
    width = 1020
    height = 190 + max(len(included_categories), 1) * 70
    left, plot_width, top = 250, 470, 135
    parts = svg_start(
        width,
        height,
        "Answer correctness by question category",
        f"Mean scores with 95% bootstrap intervals; categories with fewer than {min_n} questions omitted.",
    )
    if not included_categories:
        parts.append(
            svg_text(
                width / 2,
                160,
                f"No category has at least {min_n} questions in this run.",
                "label",
                "middle",
            )
        )
        parts.append("</svg>")
        output_path.write_text("\n".join(parts), encoding="utf-8")
        return

    for tick in range(0, 11, 2):
        x = left + plot_width * tick / 10
        parts.append(
            f'<line x1="{x:.1f}" y1="110" x2="{x:.1f}" y2="{height - 55}" '
            'stroke="#e3e8ed" stroke-width="1"/>'
        )
        parts.append(svg_text(x, height - 31, f"{tick / 10:.1f}", "small", "middle"))
    for system, color, legend_y in (
        ("RAG", COLORS["RAG"], 88),
        ("Baseline", COLORS["Baseline"], 88),
    ):
        legend_x = 810 if system == "RAG" else 900
        parts.append(
            f'<circle cx="{legend_x}" cy="{legend_y - 4}" r="5" fill="{color}"/>'
        )
        parts.append(svg_text(legend_x + 10, legend_y, system, "small"))

    for index, category in enumerate(included_categories):
        group = summary.loc[summary["category"] == category]
        n = int(group.loc[group["system"] == "RAG", "n"].iloc[0])
        center_y = top + index * 70
        parts.append(svg_text(20, center_y - 1, category.replace("_", " ").title()))
        parts.append(svg_text(20, center_y + 17, f"n={n}", "small"))
        for offset, system in ((-9, "RAG"), (9, "Baseline")):
            row = group.loc[group["system"] == system].iloc[0]
            mean = float(row["mean_answer_correctness"])
            low, high = float(row["ci_95_low"]), float(row["ci_95_high"])
            y = center_y + offset
            x_low = left + plot_width * low
            x_high = left + plot_width * high
            x_mean = left + plot_width * mean
            parts.append(
                f'<line x1="{x_low:.1f}" y1="{y}" x2="{x_high:.1f}" y2="{y}" '
                f'stroke="{COLORS[system]}" stroke-width="3"/>'
            )
            parts.append(
                f'<circle cx="{x_mean:.1f}" cy="{y}" r="5" fill="{COLORS[system]}"/>'
            )
    parts.append(
        svg_text(
            left + plot_width / 2,
            height - 8,
            "Mean correctness score (0–1)",
            "small",
            "middle",
        )
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    frame = read_scores(args.report, args.dataset)
    metrics = metric_summary(frame)
    paired = paired_summary(frame)
    categories = category_summary(frame)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metrics.to_csv(
        args.output_dir / "metric_summary.csv", index=False, float_format="%.4f"
    )
    paired.to_csv(
        args.output_dir / "paired_comparison.csv", index=False, float_format="%.4f"
    )
    categories.to_csv(
        args.output_dir / "category_summary.csv", index=False, float_format="%.4f"
    )
    make_paired_difference_chart(paired, args.output_dir / "rag_vs_baseline.svg")
    make_evidence_distribution_chart(
        frame, metrics, args.output_dir / "rag_evidence_metrics.svg"
    )
    make_category_chart(categories, args.output_dir / "category_correctness.svg")

    print(f"Saved paired comparison: {args.output_dir / 'paired_comparison.csv'}")
    print(f"Saved metric summary: {args.output_dir / 'metric_summary.csv'}")
    print(f"Saved category summary: {args.output_dir / 'category_summary.csv'}")
    print(f"Saved figures in {args.output_dir}")
    if len(frame.loc[frame["system"] == "RAG"]) < 30:
        print(
            "Pilot sample detected: treat these figures as exploratory, not final findings."
        )
    print(
        "Bootstrap intervals describe resampling variability in this reviewed set; "
        "they are not a standalone significance test."
    )


if __name__ == "__main__":
    main()
