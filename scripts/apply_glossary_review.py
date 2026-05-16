#!/usr/bin/env python3
"""Apply manual ruby review CSVs to a cleaned glossary."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


KATAKANA_TAIL = re.compile(r"^(.*?)([ァ-ヴー][ァ-ヴー・=\sA-Za-z0-9.-]*)$")
ASCII_TAIL = re.compile(r"^(.+?)([A-Za-z][A-Za-z0-9 .'-]*)$")
KNOWN_ZH_RT = ("诺斯替主义", "路西法", "撒旦", "恶魔", "倒吊人")


def clean(value: Any) -> str:
    return str(value or "").strip()


def ruby_html(base: str, reading: str) -> str:
    base = clean(base)
    reading = clean(reading)
    if not base or not reading:
        return ""
    return f"<ruby>{base}<rt>{reading}</rt></ruby>"


def normalize_mode(value: str) -> str:
    value = clean(value).lower()
    aliases = {
        "nomal": "normal",
        "ruby": "normal",
        "ordinary": "normal",
        "special_ruby": "special",
        "gikun": "special",
        "none": "none",
        "": "",
    }
    return aliases.get(value, value)


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def split_jp_special(raw_source: str) -> tuple[str, str]:
    match = KATAKANA_TAIL.match(raw_source)
    if not match:
        return raw_source, ""
    base, reading = clean(match.group(1)), clean(match.group(2))
    return (base or raw_source), reading


def split_zh_special(zh: str) -> tuple[str, str]:
    ascii_match = ASCII_TAIL.match(zh)
    if ascii_match:
        return clean(ascii_match.group(1)), clean(ascii_match.group(2))
    for rt in KNOWN_ZH_RT:
        if zh.endswith(rt) and len(zh) > len(rt):
            return zh[: -len(rt)], rt
    return zh, ""


def apply_uncertain(rows_by_raw: dict[str, dict[str, str]], uncertain_rows: list[dict[str, str]]) -> int:
    changed = 0
    for review in uncertain_rows:
        raw = clean(review.get("raw_source"))
        row = rows_by_raw.get(raw)
        if row is None:
            continue
        correct_source = clean(review.get("correct_source"))
        correct_reading = clean(review.get("correct_reading"))
        mode = normalize_mode(review.get("correct_ruby_mode", ""))
        rich_source = clean(review.get("correct_rich_source"))
        rich_zh = clean(review.get("correct_rich_zh"))
        if not any((correct_source, correct_reading, mode, rich_source, rich_zh)):
            continue
        if correct_source:
            row["source"] = correct_source
        if correct_reading:
            row["reading"] = correct_reading
        if mode:
            row["ruby_mode"] = mode
        if rich_source:
            row["rich_source"] = rich_source
        elif row.get("source") and row.get("reading") and row.get("ruby_mode") in {"normal", "special"}:
            row["rich_source"] = ruby_html(row["source"], row["reading"])
        if rich_zh:
            row["rich_zh"] = rich_zh
        row["status"] = "draft"
        row["note"] = append_note(row.get("note", ""), "applied manual uncertain ruby review")
        changed += 1
    return changed


def apply_auto_special_lines(
    rows_by_raw: dict[str, dict[str, str]],
    auto_rows: list[dict[str, str]],
    line_numbers: set[int],
) -> int:
    changed = 0
    for csv_index, auto in enumerate(auto_rows, start=2):
        if csv_index not in line_numbers:
            continue
        raw = clean(auto.get("raw_source"))
        row = rows_by_raw.get(raw)
        if row is None:
            continue
        source, reading = split_jp_special(raw)
        zh_base, zh_rt = split_zh_special(row.get("zh", ""))
        row["source"] = source
        row["reading"] = reading
        row["ruby_mode"] = "special"
        row["rich_source"] = ruby_html(source, reading)
        row["rich_zh"] = ruby_html(zh_base, zh_rt) if zh_rt else ""
        row["note"] = append_note(row.get("note", ""), f"manual override from auto_ruby_review line {csv_index}: special ruby")
        changed += 1
    return changed


def append_note(note: str, extra: str) -> str:
    note = clean(note)
    return f"{note} | {extra}" if note else extra


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply reviewed ruby corrections to cleaned glossary")
    parser.add_argument("--cleaned", required=True)
    parser.add_argument("--uncertain-csv")
    parser.add_argument("--auto-ruby-csv")
    parser.add_argument("--auto-special-lines", default="", help="Comma-separated CSV line numbers, including header line")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cleaned_path = Path(args.cleaned)
    rows = read_csv(cleaned_path)
    if not rows:
        raise SystemExit(f"No rows found: {cleaned_path}")
    fields = list(rows[0].keys())
    rows_by_raw = {row.get("raw_source", ""): row for row in rows if row.get("raw_source")}

    uncertain_changed = apply_uncertain(rows_by_raw, read_csv(Path(args.uncertain_csv) if args.uncertain_csv else None))
    line_numbers = {int(part) for part in args.auto_special_lines.split(",") if part.strip().isdigit()}
    auto_changed = apply_auto_special_lines(
        rows_by_raw,
        read_csv(Path(args.auto_ruby_csv) if args.auto_ruby_csv else None),
        line_numbers,
    )
    write_csv(Path(args.output), rows, fields)
    print(f"Wrote reviewed glossary: {args.output}")
    print(f"Applied uncertain rows: {uncertain_changed}")
    print(f"Applied auto special overrides: {auto_changed}")


if __name__ == "__main__":
    main()
