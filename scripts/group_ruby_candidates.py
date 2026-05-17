#!/usr/bin/env python3
"""Group OCR-level ruby candidate boxes into review-friendly reading rows."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean
from typing import Any


FIELDS = [
    "page",
    "file",
    "reading_joined",
    "reading_parts",
    "part_count",
    "score_min",
    "score_avg",
    "x1",
    "y1",
    "x2",
    "y2",
    "near_text",
    "near_x_distance_avg",
    "reason",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(clean(value))
    except ValueError:
        return default


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def row_cx(row: dict[str, str]) -> float:
    return (number(row.get("x1")) + number(row.get("x2"))) / 2


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return clean(row.get("page")), clean(row.get("file")), clean(row.get("near_text"))


def can_merge_text(left: str, right: str) -> bool:
    left_len = len(left)
    right_len = len(right)
    if left_len >= 3 and right_len >= 3:
        return False
    if min(left_len, right_len) <= 1 and max(left_len, right_len) > 4:
        return False
    return True


def flush_group(group: list[dict[str, str]], output: list[dict[str, Any]]) -> None:
    if not group:
        return
    scores = [number(row.get("score"), -1.0) for row in group if clean(row.get("score"))]
    distances = [number(row.get("near_x_distance")) for row in group if clean(row.get("near_x_distance"))]
    output.append(
        {
            "page": group[0].get("page", ""),
            "file": group[0].get("file", ""),
            "reading_joined": "".join(row.get("text", "") for row in group),
            "reading_parts": "|".join(row.get("text", "") for row in group),
            "part_count": len(group),
            "score_min": round(min(scores), 4) if scores else "",
            "score_avg": round(mean(scores), 4) if scores else "",
            "x1": round(min(number(row.get("x1")) for row in group), 2),
            "y1": round(min(number(row.get("y1")) for row in group), 2),
            "x2": round(max(number(row.get("x2")) for row in group), 2),
            "y2": round(max(number(row.get("y2")) for row in group), 2),
            "near_text": group[0].get("near_text", ""),
            "near_x_distance_avg": round(mean(distances), 2) if distances else "",
            "reason": "grouped adjacent ruby boxes for review" if len(group) > 1 else "single ruby box",
        }
    )


def group_rows(rows: list[dict[str, str]], max_x_delta: float = 10.0, max_y_gap: float = 16.0) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    rows = sorted(rows, key=lambda row: (row_key(row), row_cx(row), number(row.get("y1"))))
    current: list[dict[str, str]] = []
    current_key: tuple[str, str, str] | None = None
    current_cx = 0.0
    last_y2 = 0.0

    for row in rows:
        key = row_key(row)
        cx = row_cx(row)
        y1 = number(row.get("y1"))
        y2 = number(row.get("y2"))
        same_group = (
            current
            and key == current_key
            and abs(cx - current_cx) <= max_x_delta
            and y1 - last_y2 <= max_y_gap
            and can_merge_text(current[-1].get("text", ""), row.get("text", ""))
        )
        if not same_group:
            flush_group(current, grouped)
            current = [row]
            current_key = key
            current_cx = cx
            last_y2 = y2
            continue
        current.append(row)
        current_cx = mean([current_cx, cx])
        last_y2 = max(last_y2, y2)

    flush_group(current, grouped)
    return grouped


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in FIELDS} for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Group ruby_candidates.csv into review-friendly rows")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-x-delta", type=float, default=10.0)
    parser.add_argument("--max-y-gap", type=float, default=16.0)
    args = parser.parse_args()

    rows = read_rows(Path(args.input))
    grouped = group_rows(rows, args.max_x_delta, args.max_y_gap)
    write_rows(Path(args.output), grouped)
    print(f"Wrote grouped ruby candidates: {args.output}")
    print(f"Input rows: {len(rows)}")
    print(f"Grouped rows: {len(grouped)}")


if __name__ == "__main__":
    main()
