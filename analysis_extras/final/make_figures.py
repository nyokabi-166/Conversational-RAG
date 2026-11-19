"""Draw thesis figures from the post-processed evaluation tables.

Pillow is used because matplotlib is not installed. Each figure is written as a
300-dpi PNG plus a simple SVG. Run after post_eval.py:

    backend\\.venv\\Scripts\\python.exe analysis_extras\\final\\make_figures.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "analysis_extras" / "final"
REVIEW = ROOT / "analysis_extras"

RAG_COLOR = (176, 30, 40)
BASELINE_COLOR = (107, 114, 128)
INK = (31, 41, 55)
GRID = (226, 232, 240)
BACKGROUND = (255, 255, 255)
AGREE_COLOR = (220, 252, 231)
DISAGREE_COLOR = (254, 226, 226)
FONT = Path("C:/Windows/Fonts/arial.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")

LABELS = {
    "faithfulness": "Faithfulness",
    "context_recall": "Context recall",
    "answer_relevancy": "Answer relevancy",
    "answer_correctness": "Answer correctness",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)


def kappa_text(value: object) -> str:
    return "undefined" if value is None else f"{float(value):.3f}"


def draw_grouped(
    title: str,
    groups: list[str],
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    out_stem: str,
    width: int = 2400,
    height: int = 1350,
    legend: bool = True,
    max_value: float = 1.0,
    tick_count: int = 5,
    value_format: str = "{:.2f}",
) -> None:
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    margin_left, margin_right = 230, 90
    margin_top, margin_bottom = 190, 180
    plot = (
        margin_left,
        margin_top,
        width - margin_right,
        height - margin_bottom,
    )
    x0, y0, x1, y1 = plot

    draw.text((margin_left, 70), title, font=font(58, bold=True), fill=INK)

    for tick in range(tick_count + 1):
        value = max_value * tick / tick_count
        y = y1 - (y1 - y0) * (value / max_value)
        draw.line((x0, y, x1, y), fill=GRID, width=2)
        draw.text(
            (x0 - 18, y),
            value_format.format(value),
            font=font(30),
            fill=INK,
            anchor="rm",
        )

    draw.line((x0, y0, x0, y1), fill=INK, width=3)
    draw.line((x0, y1, x1, y1), fill=INK, width=3)

    group_width = (x1 - x0) / max(len(groups), 1)
    bar_width = group_width / (len(series) + 1)
    for group_index, group in enumerate(groups):
        base_center = x0 + group_width * (group_index + 0.5)
        for series_index, (_, values, color) in enumerate(series):
            value = max(0.0, min(max_value, float(values[group_index])))
            center = (
                base_center
                + (series_index - (len(series) - 1) / 2) * bar_width
            )
            left = center - bar_width * 0.42
            right = center + bar_width * 0.42
            top = y1 - (y1 - y0) * (value / max_value)
            draw.rounded_rectangle(
                (left, top, right, y1), radius=8, fill=color
            )
            draw.text(
                ((left + right) / 2, top - 14),
                value_format.format(value),
                font=font(30, bold=True),
                fill=INK,
                anchor="mb",
            )
        draw.text(
            (base_center, y1 + 34),
            group,
            font=font(32),
            fill=INK,
            anchor="ma",
        )

    if legend:
        legend_y = 120
        item_widths = [
            44 + 16 + int(draw.textlength(label, font=font(32))) + 56
            for label, _, _ in series
        ]
        legend_x = x1 - sum(item_widths)
        for (label, _, color), item_width in zip(series, item_widths):
            draw.rounded_rectangle(
                (legend_x, legend_y - 18, legend_x + 44, legend_y + 18),
                radius=6,
                fill=color,
            )
            draw.text(
                (legend_x + 60, legend_y),
                label,
                font=font(32),
                fill=INK,
                anchor="lm",
            )
            legend_x += item_width

    image.save(FINAL / f"{out_stem}.png", dpi=(300, 300))
    write_svg(
        title,
        groups,
        series,
        FINAL / f"{out_stem}.svg",
        max_value=max_value,
        tick_count=tick_count,
        value_format=value_format,
    )


def write_svg(
    title: str,
    groups: list[str],
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    path: Path,
    width: int = 800,
    height: int = 450,
    max_value: float = 1.0,
    tick_count: int = 5,
    value_format: str = "{:.2f}",
) -> None:
    left, top, right, bottom = 80, 60, width - 30, height - 60
    plot_width = right - left
    plot_height = bottom - top
    group_width = plot_width / max(len(groups), 1)
    bar_width = group_width / (len(series) + 1)
    colors = {label: color for label, _, color in series}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        f'<text x="{left}" y="32" font-family="Arial" font-size="22" '
        f'font-weight="bold" fill="#1f2937">{title}</text>',
    ]
    for tick in range(tick_count + 1):
        value = max_value * tick / tick_count
        y = bottom - plot_height * value / max_value
        parts.append(
            f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" '
            f'stroke="#e2e8f0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4}" font-family="Arial" font-size="11" '
            f'text-anchor="end" fill="#1f2937">{value_format.format(value)}</text>'
        )
    for group_index, group in enumerate(groups):
        center = left + group_width * (group_index + 0.5)
        for series_index, (label, values, _) in enumerate(series):
            value = max(0.0, min(max_value, float(values[group_index])))
            x = center + (series_index - (len(series) - 1) / 2) * bar_width
            bar_height = plot_height * value / max_value
            color = "#%02x%02x%02x" % colors[label]
            parts.append(
                f'<rect x="{x - bar_width * 0.42:.1f}" y="{bottom - bar_height:.1f}" '
                f'width="{bar_width * 0.84:.1f}" height="{bar_height:.1f}" fill="{color}" rx="3"/>'
            )
            parts.append(
                f'<text x="{x:.1f}" y="{bottom - bar_height - 4:.1f}" '
                f'font-family="Arial" font-size="11" text-anchor="middle" '
                f'fill="#1f2937">{value_format.format(value)}</text>'
            )
        parts.append(
            f'<text x="{center:.1f}" y="{bottom + 18}" font-family="Arial" '
            f'font-size="11" text-anchor="middle" fill="#1f2937">{group}</text>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def overall_figure() -> None:
    overall = pd.read_csv(FINAL / "overall_metrics.csv")
    rag = overall[overall["system"] == "RAG"].iloc[0]
    baseline = overall[overall["system"] == "Baseline"].iloc[0]

    rag_metrics = [label for label in LABELS if f"{label}_mean" in rag]
    draw_grouped(
        "RAG answer quality (RAGAS)",
        [LABELS[label] for label in rag_metrics],
        [("RAG", [float(rag[f"{label}_mean"]) for label in rag_metrics], RAG_COLOR)],
        "fig_ragas_overall",
    )

    shared = ["answer_relevancy", "answer_correctness"]
    draw_grouped(
        "RAG vs no-retrieval baseline",
        [LABELS[label] for label in shared],
        [
            ("RAG", [float(rag[f"{label}_mean"]) for label in shared], RAG_COLOR),
            (
                "Baseline",
                [float(baseline[f"{label}_mean"]) for label in shared],
                BASELINE_COLOR,
            ),
        ],
        "fig_rag_vs_baseline",
    )


def category_figure() -> None:
    path = FINAL / "category_metrics.csv"
    if not path.is_file():
        return
    table = pd.read_csv(path)
    column = "answer_correctness_mean"
    table = table[table[column].notna()]
    categories = list(dict.fromkeys(table["category"]))
    by_system = {
        system: [
            float(
                table[(table["category"] == category) & (table["system"] == system)][
                    column
                ].mean()
            )
            for category in categories
        ]
        for system in ("RAG", "Baseline")
    }
    draw_grouped(
        "Answer correctness by question category",
        [str(category).replace("_", " ") for category in categories],
        [
            ("RAG", by_system["RAG"], RAG_COLOR),
            ("Baseline", by_system["Baseline"], BASELINE_COLOR),
        ],
        "fig_category_correctness",
        width=3000,
    )


def consistency_figure() -> None:
    path = FINAL / "consistency_summary.csv"
    if not path.is_file():
        return
    row = pd.read_csv(path).iloc[0]
    draw_grouped(
        "Response consistency (3 runs per question)",
        ["Identical answers", "Any refusal"],
        [
            (
                "Final build",
                [
                    float(row["identical_rate"]),
                    float(row["any_refusal_rate"]),
                ],
                RAG_COLOR,
            )
        ],
        "fig_consistency",
        width=1800,
        height=1200,
        legend=False,
    )


def count_values(series: pd.Series, order: list[str]) -> list[int]:
    values = series.fillna("").astype(str).str.strip().value_counts()
    return [int(values.get(item, 0)) for item in order]


def unanswerable_figure() -> None:
    path = REVIEW / "unanswerable_review.csv"
    if not path.is_file():
        print("skip fig_unanswerable_behaviour: review file missing")
        return
    table = pd.read_csv(path)
    if "rag_type" not in table.columns or "baseline_type" not in table.columns:
        print("skip fig_unanswerable_behaviour: label columns missing")
        return
    if table[["rag_type", "baseline_type"]].fillna("").astype(str).apply(
        lambda column: column.str.strip().eq("").all()
    ).all():
        print("skip fig_unanswerable_behaviour: labels are empty")
        return

    order = ["refused", "partial_refusal", "hallucinated", "off_topic"]
    labels = ["Refused", "Partial refusal", "Hallucinated", "Off topic"]
    rag = count_values(table["rag_type"], order)
    baseline = count_values(table["baseline_type"], order)
    max_count = max(rag + baseline + [1])
    max_value = float(max_count + 1)
    draw_grouped(
        f"Unanswerable questions: response behaviour (counts, n={len(table)})",
        labels,
        [
            ("RAG", [float(value) for value in rag], RAG_COLOR),
            ("Baseline", [float(value) for value in baseline], BASELINE_COLOR),
        ],
        "fig_unanswerable_behaviour",
        width=2400,
        height=1350,
        max_value=max_value,
        tick_count=int(max_value),
        value_format="{:.0f}",
    )


def draw_agreement_matrix(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    metrics: dict[str, object],
    threshold: str,
) -> None:
    cell_w, cell_h = 280, 190
    draw.text(
        (x0 + cell_w, y0 - 80),
        f"RAGAS threshold {threshold}",
        font=font(36, bold=True),
        fill=INK,
        anchor="ma",
    )
    for column, label in enumerate(("Fail", "Pass")):
        draw.text(
            (x0 + cell_w * (column + 1), y0 - 22),
            label,
            font=font(30),
            fill=INK,
            anchor="mb",
        )
    for row, label in enumerate(("Human 1", "Human 0")):
        draw.text(
            (x0 - 20, y0 + cell_h * (row + 0.5)),
            label,
            font=font(30),
            fill=INK,
            anchor="rm",
        )

    cells = [
        [metrics.get("fn", 0), metrics.get("tp", 0)],
        [metrics.get("tn", 0), metrics.get("fp", 0)],
    ]
    for row in range(2):
        for column in range(2):
            agreed = (row == 0 and column == 1) or (row == 1 and column == 0)
            left = x0 + cell_w * column
            top = y0 + cell_h * row
            draw.rectangle(
                (left, top, left + cell_w, top + cell_h),
                fill=AGREE_COLOR if agreed else DISAGREE_COLOR,
                outline=INK,
                width=3,
            )
            draw.text(
                (left + cell_w / 2, top + cell_h / 2),
                f"{int(cells[row][column])}",
                font=font(54, bold=True),
                fill=INK,
                anchor="mm",
            )

    draw.text(
        (x0, y0 + 2 * cell_h + 38),
        f"n={metrics.get('n', 0)}   agreement={float(metrics.get('percent_agreement', 0)):.1f}%   kappa={kappa_text(metrics.get('kappa'))}",
        font=font(30, bold=True),
        fill=INK,
        anchor="la",
    )


def write_agreement_svg(
    data: dict[str, object], path: Path
) -> None:
    validation = data["validation_agreement"]
    width, height = 1100, 650
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        '<text x="60" y="48" font-family="Arial" font-size="24" font-weight="bold" fill="#1f2937">Human versus RAGAS answer correctness</text>',
    ]
    for index, threshold in enumerate(("0.5", "0.7")):
        metrics = validation["thresholds"][threshold]
        x0 = 150 + index * 500
        y0 = 220
        cell_w, cell_h = 170, 105
        parts.append(
            f'<text x="{x0 + cell_w}" y="{y0 - 45}" font-family="Arial" font-size="17" font-weight="bold" text-anchor="middle" fill="#1f2937">RAGAS threshold {threshold}</text>'
        )
        for column, label in enumerate(("Fail", "Pass")):
            parts.append(
                f'<text x="{x0 + cell_w * (column + 1)}" y="{y0 - 12}" font-family="Arial" font-size="14" text-anchor="middle" fill="#1f2937">{label}</text>'
            )
        for row, label in enumerate(("Human 1", "Human 0")):
            parts.append(
                f'<text x="{x0 - 12}" y="{y0 + cell_h * (row + 0.5) + 5}" font-family="Arial" font-size="14" text-anchor="end" fill="#1f2937">{label}</text>'
            )
        cells = [
            [metrics.get("fn", 0), metrics.get("tp", 0)],
            [metrics.get("tn", 0), metrics.get("fp", 0)],
        ]
        for row in range(2):
            for column in range(2):
                agreed = (row == 0 and column == 1) or (row == 1 and column == 0)
                fill = "#dcfce7" if agreed else "#fee2e2"
                left = x0 + cell_w * column
                top = y0 + cell_h * row
                parts.append(
                    f'<rect x="{left}" y="{top}" width="{cell_w}" height="{cell_h}" fill="{fill}" stroke="#1f2937" stroke-width="2"/>'
                )
                parts.append(
                    f'<text x="{left + cell_w / 2}" y="{top + cell_h / 2 + 6}" font-family="Arial" font-size="28" font-weight="bold" text-anchor="middle" fill="#1f2937">{int(cells[row][column])}</text>'
                )
        parts.append(
            f'<text x="{x0}" y="{y0 + 2 * cell_h + 28}" font-family="Arial" font-size="14" font-weight="bold" fill="#1f2937">n={metrics.get("n", 0)}  agreement={float(metrics.get("percent_agreement", 0)):.1f}%  kappa={kappa_text(metrics.get("kappa"))}</text>'
        )
    answerable = validation.get("answerable_only", {})
    if answerable.get("n_labeled"):
        a05 = answerable["thresholds"]["0.5"]
        a07 = answerable["thresholds"]["0.7"]
        parts.append(
            f'<text x="60" y="{height - 42}" font-family="Arial" font-size="11" fill="#1f2937">Answerable-only sensitivity: n={answerable.get("n_labeled")}; threshold 0.5 agreement={float(a05["percent_agreement"]):.1f}% kappa={kappa_text(a05.get("kappa"))}; threshold 0.7 agreement={float(a07["percent_agreement"]):.1f}% kappa={kappa_text(a07.get("kappa"))}</text>'
        )
    parts.append(
        '<text x="60" y="610" font-family="Arial" font-size="12" fill="#4b5563">Human 0 = incorrect; Human 1 = correct. RAGAS fail = score below threshold; pass = score at or above threshold.</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def agreement_figure() -> None:
    path = FINAL / "agreement_results.json"
    if not path.is_file():
        print("skip fig_human_judge_agreement: agreement_results.json missing")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    validation = data.get("validation_agreement", {})
    if not validation.get("n_labeled"):
        print("skip fig_human_judge_agreement: validation labels are empty")
        return

    image = Image.new("RGB", (2600, 1600), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text(
        (230, 70),
        "Human versus RAGAS answer correctness",
        font=font(58, bold=True),
        fill=INK,
    )
    for index, threshold in enumerate(("0.5", "0.7")):
        draw_agreement_matrix(
            draw,
            360 + index * 1050,
            390,
            validation["thresholds"][threshold],
            threshold,
        )
    answerable = validation.get("answerable_only", {})
    if answerable.get("n_labeled"):
        values = []
        for threshold in ("0.5", "0.7"):
            metrics = answerable["thresholds"][threshold]
            values.append(
                f"threshold {threshold}: agreement={float(metrics['percent_agreement']):.1f}%, kappa={kappa_text(metrics.get('kappa'))}"
            )
        draw.text(
            (230, 1240),
            f"Answerable-only sensitivity (n={answerable['n_labeled']}): " + "; ".join(values),
            font=font(28),
            fill=INK,
        )
    draw.text(
        (230, 1330),
        "Human 0 = incorrect; Human 1 = correct. RAGAS fail = score below threshold; pass = score at or above threshold.",
        font=font(28),
        fill=INK,
    )
    image.save(FINAL / "fig_human_judge_agreement.png", dpi=(300, 300))
    write_agreement_svg(data, FINAL / "fig_human_judge_agreement.svg")


def draw_hbar_counts(
    title: str,
    labels: list[str],
    values: list[int],
    out_stem: str,
) -> None:
    width = 2400
    height = max(900, 260 + 120 * len(labels))
    margin_left, margin_right = 620, 180
    margin_top, margin_bottom = 220, 130
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    x0, y0 = margin_left, margin_top
    x1, y1 = width - margin_right, height - margin_bottom
    max_value = max(values + [1])
    draw.text((x0, 70), title, font=font(54, bold=True), fill=INK)
    for tick in range(6):
        value = max_value * tick / 5
        x = x0 + (x1 - x0) * tick / 5
        draw.line((x, y0, x, y1), fill=GRID, width=2)
        draw.text(
            (x, y1 + 18),
            f"{value:.0f}",
            font=font(28),
            fill=INK,
            anchor="ma",
        )
    draw.line((x0, y0, x0, y1), fill=INK, width=3)
    draw.line((x0, y1, x1, y1), fill=INK, width=3)
    row_height = (y1 - y0) / max(len(labels), 1)
    for index, (label, value) in enumerate(zip(labels, values)):
        center = y0 + row_height * (index + 0.5)
        draw.text(
            (x0 - 24, center),
            label,
            font=font(30),
            fill=INK,
            anchor="rm",
        )
        right = x0 + (x1 - x0) * value / max_value
        draw.rounded_rectangle(
            (x0, center - row_height * 0.30, right, center + row_height * 0.30),
            radius=8,
            fill=RAG_COLOR,
        )
        draw.text(
            (right + 16, center),
            str(value),
            font=font(30, bold=True),
            fill=INK,
            anchor="lm",
        )
    image.save(FINAL / f"{out_stem}.png", dpi=(300, 300))

    svg_width, svg_height = 1000, max(420, 120 + 55 * len(labels))
    left, top = 300, 100
    right, bottom = svg_width - 60, svg_height - 50
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">',
        f'<rect width="{svg_width}" height="{svg_height}" fill="#fff"/>',
        f'<text x="40" y="38" font-family="Arial" font-size="22" font-weight="bold" fill="#1f2937">{title}</text>',
    ]
    for tick in range(6):
        value = max_value * tick / 5
        x = left + (right - left) * tick / 5
        parts.append(
            f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="#e2e8f0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x}" y="{bottom + 16}" font-family="Arial" font-size="11" text-anchor="middle" fill="#1f2937">{value:.0f}</text>'
        )
    row_height = (bottom - top) / max(len(labels), 1)
    for index, (label, value) in enumerate(zip(labels, values)):
        center = top + row_height * (index + 0.5)
        parts.append(
            f'<text x="{left - 10}" y="{center + 4}" font-family="Arial" font-size="12" text-anchor="end" fill="#1f2937">{label}</text>'
        )
        bar_right = left + (right - left) * value / max_value
        parts.append(
            f'<rect x="{left}" y="{center - row_height * 0.28}" width="{bar_right - left}" height="{row_height * 0.56}" fill="#b01e28" rx="3"/>'
        )
        parts.append(
            f'<text x="{bar_right + 6}" y="{center + 4}" font-family="Arial" font-size="12" font-weight="bold" fill="#1f2937">{value}</text>'
        )
    parts.append("</svg>")
    (FINAL / f"{out_stem}.svg").write_text("\n".join(parts), encoding="utf-8")


def error_cause_figure() -> None:
    path = REVIEW / "error_analysis_starter_DRAFT.csv"
    if not path.is_file():
        print("skip fig_error_causes: review file missing")
        return
    table = pd.read_csv(path)
    if "my_confirmed_cause" not in table.columns:
        print("skip fig_error_causes: label column missing")
        return
    series = table["my_confirmed_cause"].fillna("").astype(str).str.strip()
    series = series[series != ""]
    if series.empty:
        print("skip fig_error_causes: labels are empty")
        return
    counts = series.value_counts()
    labels = [str(value).replace("_", " ") for value in counts.index]
    values = [int(value) for value in counts.values]
    draw_hbar_counts(
        f"Confirmed error causes (n={len(series)})",
        labels,
        values,
        "fig_error_causes",
    )


def main() -> None:
    global FINAL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=FINAL)
    args = parser.parse_args()
    FINAL = args.dir
    FINAL.mkdir(parents=True, exist_ok=True)
    overall_figure()
    category_figure()
    consistency_figure()
    unanswerable_figure()
    agreement_figure()
    error_cause_figure()
    for path in sorted(FINAL.glob("fig_*")):
        print(path)


if __name__ == "__main__":
    main()
