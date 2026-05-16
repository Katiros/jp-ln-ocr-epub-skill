#!/usr/bin/env python3
"""Build the small glossary that is safe to send to the translator prompt."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


JAPANESE_RE = re.compile(r"[一-龯々ぁ-ゖァ-ヴー]")
BAD_SOURCE_RE = re.compile(r"[\s\r\n\t]|^[・=＝、。，．,.!?！？:：;；「」『』（）()]+|[、。，．,.!?！？:：;；「」『』（）()]+$")
FIELDS = ["source", "reading", "zh", "type", "status", "confidence", "source_hint", "reason", "note"]
DEFAULT_BOUNDARY_TERMS = ("アリス", "アンナ", "コロンゾン", "上条")


def clean(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def normalize_status(value: str) -> str:
    return value.lower().strip()


def normalize_confidence(value: str) -> str:
    value = value.lower().strip()
    if value in {"confirmed", "high", "medium", "low"}:
        return value
    return ""


def has_stuck_boundary_term(source: str, boundary_terms: tuple[str, ...]) -> bool:
    separators = {"=", "＝", "・", "／", "/", " "}
    for term in boundary_terms:
        start = source.find(term)
        while start > 0:
            if source[start - 1] not in separators:
                return True
            start = source.find(term, start + len(term))
    return False


def should_include(
    row: dict[str, str],
    min_confidence: str,
    max_source_length: int,
    boundary_terms: tuple[str, ...],
) -> tuple[bool, str]:
    source = clean(row.get("source"))
    zh = clean(row.get("zh"))
    status = normalize_status(row.get("status", ""))
    confidence = normalize_confidence(row.get("confidence", ""))
    note = clean(row.get("note"))

    if not source:
        return False, "empty source"
    if not zh:
        return False, "empty zh"
    if status in {"remove", "removed", "reject", "rejected", "deleted", "ignore", "ignored"}:
        return False, f"status={status}"
    if status in {"pending_review", "pending", "api_error"}:
        return False, f"status={status}"
    if len(source) <= 1:
        return False, "source too short"
    if len(source) > max_source_length:
        return False, "source too long"
    if BAD_SOURCE_RE.search(source):
        return False, "source contains whitespace or boundary punctuation"
    if has_stuck_boundary_term(source, boundary_terms):
        return False, "source appears to contain a stuck independent name"
    if not JAPANESE_RE.search(source):
        return False, "source is not Japanese-like"
    if re.search(r"(ocr|fragment|碎片|拆分|误识别|low confidence)", note, re.I):
        return False, "note marks possible OCR fragment"

    if status == "confirmed":
        return True, "confirmed"

    order = {"low": 0, "medium": 1, "high": 2, "confirmed": 3}
    required = order.get(min_confidence, 1)
    actual = order.get(confidence, 0)
    if status == "draft" and actual >= required:
        return True, f"draft confidence={confidence or 'missing'}"
    return False, f"status={status or 'missing'} confidence={confidence or 'missing'}"


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    chosen: dict[str, dict[str, str]] = {}
    score = {"confirmed": 30, "high": 20, "medium": 10, "low": 0, "": 0}
    for row in rows:
        source = clean(row.get("source"))
        if not source:
            continue
        status = normalize_status(row.get("status", ""))
        confidence = normalize_confidence(row.get("confidence", ""))
        row_score = score.get(confidence, 0) + (100 if status == "confirmed" else 0)
        old = chosen.get(source)
        if old is None:
            row["_score"] = str(row_score)
            chosen[source] = row
            continue
        if row_score > int(old.get("_score", "0")):
            row["_score"] = str(row_score)
            chosen[source] = row
    return [chosen[key] for key in sorted(chosen)]


def write_translation_glossary(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# 翻译用术语表",
        "# 仅作为译名参考，不要机械替换；如果某条术语明显不是当前上下文中的独立词，请忽略。",
        "",
    ]
    for row in rows:
        source = clean(row.get("source"))
        zh = clean(row.get("zh"))
        reading = clean(row.get("reading"))
        suffix = f" ({reading})" if reading else ""
        lines.append(f"{source}{suffix} → {zh}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_rejected(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{field: clean(row.get(field)) for field in FIELDS} for row in rows])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build glossary_for_translation.txt from glossary_draft.csv")
    parser.add_argument("--input", required=True, help="Usually 05_glossary/glossary_draft.csv")
    parser.add_argument("--output", required=True, help="Usually 05_glossary/glossary_for_translation.txt")
    parser.add_argument("--rejected-csv", help="Optional CSV explaining skipped rows")
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--max-source-length", type=int, default=28)
    parser.add_argument(
        "--boundary-terms",
        default=",".join(DEFAULT_BOUNDARY_TERMS),
        help="Comma-separated terms that should not appear stuck to a previous token",
    )
    args = parser.parse_args()

    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for row in read_csv(Path(args.input)):
        boundary_terms = tuple(term.strip() for term in args.boundary_terms.split(",") if term.strip())
        include, reason = should_include(row, args.min_confidence, args.max_source_length, boundary_terms)
        row["reason"] = reason
        if include:
            accepted.append(row)
        else:
            rejected.append(row)
    accepted = dedupe_rows(accepted)
    write_translation_glossary(Path(args.output), accepted)
    if args.rejected_csv:
        write_rejected(Path(args.rejected_csv), rejected)
    print(f"Wrote {len(accepted)} translation glossary rows: {args.output}")
    if args.rejected_csv:
        print(f"Wrote {len(rejected)} rejected glossary rows: {args.rejected_csv}")


if __name__ == "__main__":
    main()
