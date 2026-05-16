#!/usr/bin/env python3
"""Convert a manually copied wiki term Markdown file into glossary CSV files."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


FIELD_RE = re.compile(r"^(初出|原文|译文|譯文|英文|类型|類型|简介|簡介|备注|備註)：(.*)$")
RUBY_RE = re.compile(r"(?<=[一-龯々])([ぁ-ゖ]{2,})(?=[一-龯々]|$)")
HIRAGANA_RE = re.compile(r"[ぁ-ゖ]")
FIELDS = [
    "source",
    "reading",
    "zh",
    "ruby_mode",
    "rich_source",
    "rich_zh",
    "type",
    "status",
    "note",
    "first_seen",
    "english",
    "description",
    "raw_source",
    "ruby_candidates",
    "ruby_warnings",
]
UNCERTAIN_FIELDS = [
    "raw_source",
    "current_source",
    "zh",
    "type",
    "ruby_candidates",
    "suggested_action",
    "correct_source",
    "correct_reading",
    "correct_ruby_mode",
    "correct_rich_source",
    "correct_rich_zh",
    "note",
]
AUTO_RUBY_FIELDS = [
    "raw_source",
    "cleaned_source",
    "reading",
    "zh",
    "ruby_mode",
    "rich_source",
    "rich_zh",
    "type",
    "ruby_candidates",
    "action",
    "needs_review",
    "note",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def ruby_html(base: str, reading: str) -> str:
    base = clean(base)
    reading = clean(reading)
    if not base or not reading:
        return ""
    return f"<ruby>{base}<rt>{reading}</rt></ruby>"


def infer_ruby_mode(reading: str, warnings: str) -> str:
    if warnings.startswith("possible ruby present"):
        return "uncertain"
    if reading:
        return "normal"
    return "none"


def split_entries(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    last_key = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = FIELD_RE.match(line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if key == "初出" and current:
                entries.append(current)
                current = {}
            normalized = {
                "譯文": "译文",
                "類型": "类型",
                "簡介": "简介",
                "備註": "备注",
            }.get(key, key)
            current[normalized] = value
            last_key = normalized
        elif current and last_key:
            current[last_key] = clean(current.get(last_key) + "\n" + line)
    if current:
        entries.append(current)
    return entries


def strip_embedded_ruby(source: str, entry_type: str) -> tuple[str, str, str, str]:
    readings: list[str] = []
    candidates = [match.group(1) for match in RUBY_RE.finditer(source)]

    def repl(match: re.Match[str]) -> str:
        reading = match.group(1)
        if reading.endswith("の") and len(reading[:-1]) >= 2:
            readings.append(reading[:-1])
            return "の"
        if reading.endswith("の") and len(reading[:-1]) < 2:
            return reading
        readings.append(reading)
        return ""

    candidate = RUBY_RE.sub(repl, source)
    if not readings:
        return source, "", " ".join(candidates), ""

    if not HIRAGANA_RE.search(candidate):
        warning = "; ".join(f"removed embedded ruby: {reading}" for reading in readings)
        return candidate, " ".join(readings), " ".join(candidates), warning

    return source, "", " ".join(candidates), "possible ruby present, kept raw because ordinary hiragana also remains"


def convert_entry(entry: dict[str, str]) -> dict[str, str]:
    raw_source = clean(entry.get("原文"))
    entry_type = clean(entry.get("类型")) or "manual_wiki_term"
    source, reading, ruby_candidates, warnings = strip_embedded_ruby(raw_source, entry_type)
    ruby_mode = infer_ruby_mode(reading, warnings)
    note_parts = []
    if clean(entry.get("备注")):
        note_parts.append(clean(entry.get("备注")))
    if warnings:
        note_parts.append(warnings)
    return {
        "source": source,
        "reading": reading,
        "zh": clean(entry.get("译文")),
        "ruby_mode": ruby_mode,
        "rich_source": ruby_html(source, reading) if ruby_mode == "normal" else "",
        "rich_zh": "",
        "type": entry_type,
        "status": "draft",
        "note": " | ".join(note_parts),
        "first_seen": clean(entry.get("初出")),
        "english": clean(entry.get("英文")),
        "description": clean(entry.get("简介")),
        "raw_source": raw_source,
        "ruby_candidates": ruby_candidates,
        "ruby_warnings": warnings,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    flagged = [row for row in rows if row["ruby_warnings"] or row["raw_source"] != row["source"]]
    lines = [
        "# 手动 wiki 术语表整理报告",
        "",
        f"- 总条目数：`{len(rows)}`",
        f"- 疑似振假名混入并已清洗：`{len(flagged)}`",
        "",
        "## 需要重点复核的振假名清洗",
        "",
    ]
    if not flagged:
        lines.append("- 无")
    for row in flagged[:300]:
        lines.append(f"- `{row['raw_source']}` -> `{row['source']}` | reading=`{row['reading']}` | zh=`{row['zh']}`")
    if len(flagged) > 300:
        lines.append(f"- 还有 `{len(flagged) - 300}` 条未在报告中展开，请查看 CSV。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_uncertain_csv(path: Path, rows: list[dict[str, str]]) -> None:
    uncertain = [row for row in rows if row["ruby_warnings"].startswith("possible ruby present")]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=UNCERTAIN_FIELDS)
        writer.writeheader()
        for row in uncertain:
            writer.writerow(
                {
                    "raw_source": row["raw_source"],
                    "current_source": row["source"],
                    "zh": row["zh"],
                    "type": row["type"],
                    "ruby_candidates": row["ruby_candidates"],
                    "suggested_action": "如果是假名注音，请填写 correct_source/correct_reading；否则留空。",
                    "correct_source": "",
                    "correct_reading": "",
                    "correct_ruby_mode": "",
                    "correct_rich_source": "",
                    "correct_rich_zh": "",
                    "note": row["note"],
                }
            )


def write_auto_ruby_csv(path: Path, rows: list[dict[str, str]]) -> None:
    auto_rows = [row for row in rows if row["ruby_warnings"].startswith("removed embedded ruby")]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AUTO_RUBY_FIELDS)
        writer.writeheader()
        for row in auto_rows:
            writer.writerow(
                {
                    "raw_source": row["raw_source"],
                    "cleaned_source": row["source"],
                    "reading": row["reading"],
                    "zh": row["zh"],
                    "ruby_mode": row["ruby_mode"],
                    "rich_source": row["rich_source"],
                    "rich_zh": row["rich_zh"],
                    "type": row["type"],
                    "ruby_candidates": row["ruby_candidates"],
                    "action": "auto_removed_from_source",
                    "needs_review": "yes",
                    "note": row["note"],
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manually copied wiki terms Markdown")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-md", required=True)
    parser.add_argument("--uncertain-csv", help="Rows where embedded ruby is uncertain and needs manual mapping")
    parser.add_argument("--auto-ruby-csv", help="Rows where embedded ruby was automatically removed")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8-sig", errors="ignore")
    rows = [convert_entry(entry) for entry in split_entries(text) if clean(entry.get("原文"))]
    write_csv(Path(args.output), rows)
    write_review(Path(args.review_md), rows)
    if args.uncertain_csv:
        write_uncertain_csv(Path(args.uncertain_csv), rows)
    if args.auto_ruby_csv:
        write_auto_ruby_csv(Path(args.auto_ruby_csv), rows)
    print(f"Wrote {len(rows)} terms: {args.output}")
    print(f"Wrote review report: {args.review_md}")
    if args.uncertain_csv:
        print(f"Wrote uncertain ruby rows: {args.uncertain_csv}")
    if args.auto_ruby_csv:
        print(f"Wrote auto ruby rows: {args.auto_ruby_csv}")


if __name__ == "__main__":
    main()
