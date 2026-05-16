#!/usr/bin/env python3
"""Apply reviewed possible-special ruby rows back to a glossary CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


YES = {"yes", "y", "true", "1", "apply", "special", "ok", "\u662f", "\u5bf9", "\u5e94\u7528"}
NO = {"no", "n", "false", "0", "skip", "remove", "ignore", "\u5426", "\u4e0d", "\u8df3\u8fc7"}
REVIEW_KEYS = (
    "review",
    "decision",
    "apply",
    "use",
    "confirm",
    "\u786e\u8ba4",
    "\u8655\u7406",
    "\u5904\u7406",
    "\u662f\u5426\u56de\u5199",
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{key: clean(value) for key, value in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def decision(row: dict[str, str]) -> str:
    for key in REVIEW_KEYS:
        value = clean(row.get(key)).lower()
        if value in YES:
            return "yes"
        if value in NO:
            return "no"
    return ""


def should_apply(row: dict[str, str]) -> bool:
    mark = decision(row)
    if mark == "yes":
        return True
    if mark == "no":
        return False
    return clean(row.get("confidence")).lower() in {"high", "medium"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply possible special ruby review rows")
    parser.add_argument("--base", required=True, help="Base glossary CSV, e.g. toaru_terms_final.csv")
    parser.add_argument("--possible-special", required=True, help="Reviewed toaru_terms_possible_special.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--applied-report", required=True)
    args = parser.parse_args()

    base_rows, base_fields = read_csv(Path(args.base))
    possible_rows, _ = read_csv(Path(args.possible_special))
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for candidate in possible_rows:
        if not should_apply(candidate):
            skipped.append(candidate)
            continue
        try:
            index = int(candidate["csv_line"]) - 2
        except (KeyError, ValueError):
            skipped.append(candidate)
            continue
        if index < 0 or index >= len(base_rows):
            skipped.append(candidate)
            continue
        row = base_rows[index]
        row["source"] = clean(candidate.get("suggested_source")) or row.get("source", "")
        row["reading"] = clean(candidate.get("suggested_reading")) or row.get("reading", "")
        row["ruby_mode"] = "special"
        row["rich_source"] = clean(candidate.get("suggested_rich_source")) or row.get("rich_source", "")
        row["rich_zh"] = clean(candidate.get("suggested_rich_zh")) or row.get("rich_zh", "")
        note = row.get("note", "")
        extra = "applied possible_special review"
        row["note"] = f"{note} | {extra}" if note else extra
        applied.append(candidate)

    write_csv(Path(args.output), base_rows, base_fields)
    report_fields = [
        "csv_line",
        "source",
        "zh",
        "confidence",
        "suggested_source",
        "suggested_reading",
        "suggested_rich_source",
        "suggested_rich_zh",
        "reason",
    ]
    write_csv(Path(args.applied_report), applied, report_fields)
    print(f"Wrote glossary: {args.output}")
    print(f"Applied rows: {len(applied)}")
    print(f"Skipped rows: {len(skipped)}")
    print(f"Wrote applied report: {args.applied_report}")


if __name__ == "__main__":
    main()
