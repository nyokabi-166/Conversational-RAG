"""Validate human-review labels before agreement and figure generation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "analysis_extras" / "review_backups" / "protected_columns.json"

VALIDATION = "validation_sample.csv"
UNANSWERABLE = "unanswerable_review.csv"
ERROR_ANALYSIS = "error_analysis_starter_DRAFT.csv"

UNANSWERABLE_TYPES = {"refused", "partial_refusal", "hallucinated", "off_topic"}
SAFETY_VALUES = {"safe", "unsafe"}
ERROR_CAUSES = {
    "retrieval_miss",
    "incomplete_context",
    "generation_omission",
    "wrong_value",
    "overgeneralisation",
    "formatting",
    "judge_error",
    "other",
}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fields, rows


def protected_hash(rows: list[dict[str, str]], protected: list[str]) -> str:
    payload = "\n".join(
        "\x1f".join(
            [row["case_id"]]
            + [row[column] for column in protected if column != "case_id"]
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_binary(value: str) -> int | None:
    text = str(value).strip().lower()
    if text in {"1", "1.0", "yes", "true", "y", "t", "correct"}:
        return 1
    if text in {"0", "0.0", "no", "false", "n", "f", "incorrect", "wrong"}:
        return 0
    return None


def check_file(
    path: Path,
    manifest: dict[str, Any],
    editable: set[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "errors": [],
        "warnings": [],
    }
    if not path.is_file():
        result["errors"].append("file not found")
        return result

    fields, rows = read_rows(path)
    info = manifest["files"][path.name]
    result["row_count"] = len(rows)
    result["expected_row_count"] = info["row_count"]

    if len(rows) != info["row_count"]:
        result["errors"].append(
            f"row count {len(rows)} does not match expected {info['row_count']}"
        )

    case_ids = [row.get("case_id", "") for row in rows]
    if len(case_ids) != len(set(case_ids)):
        result["errors"].append("duplicate case_id values")
    if case_ids != info["case_ids"]:
        result["errors"].append("case_id order or contents changed")

    protected = [column for column in info["protected_columns"] if column in fields]
    if protected_hash(rows, protected) != info["protected_sha256"]:
        result["errors"].append("protected columns changed")

    result["filled"] = {
        column: sum(bool(str(row.get(column, "")).strip()) for row in rows)
        for column in sorted(editable)
        if column in fields
    }
    return result


def check_validation(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    result = check_file(path, manifest, {"my_correct", "my_supported", "my_complete", "notes"})
    if result["errors"] and result.get("row_count", 0) == 0:
        return result
    _, rows = read_rows(path)
    for row in rows:
        case_id = row.get("case_id", "")
        my_correct_val = row.get("my_correct", "")
        # Skip binary check if my_correct is blank/NaN (e.g., unanswerable rows)
        if my_correct_val is not None and str(my_correct_val).strip() != "" and parse_binary(my_correct_val) is None:
            result["errors"].append(f"{case_id}: my_correct must be 1 or 0")
        for column in ("my_supported", "my_complete"):
            value = str(row.get(column, "")).strip()
            if value and parse_binary(value) is None:
                result["errors"].append(f"{case_id}: {column} must be blank, 1, or 0")
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result


def check_unanswerable(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    result = check_file(path, manifest, {"rag_type", "baseline_type", "safety"})
    if result["errors"] and result.get("row_count", 0) == 0:
        return result
    _, rows = read_rows(path)
    for row in rows:
        case_id = row.get("case_id", "")
        for column, allowed in (
            ("rag_type", UNANSWERABLE_TYPES),
            ("baseline_type", UNANSWERABLE_TYPES),
            ("safety", SAFETY_VALUES),
        ):
            value = str(row.get(column, "")).strip()
            if not value:
                result["errors"].append(f"{case_id}: {column} is blank")
            elif value not in allowed:
                result["errors"].append(
                    f"{case_id}: {column}={value!r} is not one of {sorted(allowed)}"
                )
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result


def check_error_analysis(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    result = check_file(path, manifest, {"my_confirmed_cause", "notes"})
    if result["errors"] and result.get("row_count", 0) == 0:
        return result
    _, rows = read_rows(path)
    for row in rows:
        case_id = row.get("case_id", "")
        value = str(row.get("my_confirmed_cause", "")).strip()
        if not value:
            result["errors"].append(f"{case_id}: my_confirmed_cause is blank")
        elif value not in ERROR_CAUSES:
            result["errors"].append(
                f"{case_id}: my_confirmed_cause={value!r} is not one of "
                f"{sorted(ERROR_CAUSES)}"
            )
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.root / "analysis_extras"
    report = {
        "validation": check_validation(root / VALIDATION, manifest),
        "unanswerable": check_unanswerable(root / UNANSWERABLE, manifest),
        "error_analysis": check_error_analysis(root / ERROR_ANALYSIS, manifest),
    }
    report["status"] = (
        "PASS"
        if all(item["status"] == "PASS" for item in report.values() if isinstance(item, dict))
        else "FAIL"
    )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
