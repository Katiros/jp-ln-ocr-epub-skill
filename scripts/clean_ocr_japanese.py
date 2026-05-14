#!/usr/bin/env python3
"""First-pass cleanup for ordered Japanese OCR text.

This is intentionally conservative. It preserves section markers, flags likely
ruby contamination, extracts glossary candidates, and writes reviewable text.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


KATAKANA_TERM = re.compile(r"[ァ-ヴー]+(?:[＝=・][ァ-ヴー]+)+|[ァ-ヴー]{4,}")
KANJI_NAME = re.compile(r"[一-龯々]{2,6}")
RUBY_CONTAMINATION = re.compile(r"[一-龯々][ぁ-ゖ]{1,4}[一-龯々]|[一-龯々]{1,3}[ぁ-ゖ]{2,}")
SECTION_MARKER = re.compile(r"^\s*([0-9０-９一二三四五六七八九十]{1,3})\s*$")


def normalize_digits(text: str) -> str:
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    return text.translate(table)


def is_section_marker(line: str, prev_line: str, next_line: str) -> bool:
    match = SECTION_MARKER.match(normalize_digits(line))
    if not match:
        return False
    marker = match.group(1)
    if marker.isdigit() and int(marker) > 99:
        return False
    return bool(prev_line.strip() or next_line.strip())


def cleanup_lines(lines: list[str]) -> tuple[list[str], list[str], set[str]]:
    cleaned: list[str] = []
    warnings: list[str] = []
    glossary: set[str] = set()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            cleaned.append("")
            continue
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if is_section_marker(line, prev_line, next_line):
            cleaned.extend(["", f"## {normalize_digits(line)}", ""])
            continue
        if RUBY_CONTAMINATION.search(line):
            warnings.append(f"Possible ruby contamination: {line}")
        for term in KATAKANA_TERM.findall(line):
            glossary.add(term)
        for term in KANJI_NAME.findall(line):
            if len(term) >= 3:
                glossary.add(term)
        cleaned.append(line)
    return cleaned, warnings, glossary


def clean_file(input_path: Path, output_path: Path) -> tuple[list[str], set[str]]:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    cleaned, warnings, glossary = cleanup_lines(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(cleaned).strip() + "\n", encoding="utf-8")
    return warnings, glossary


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean ordered Japanese OCR text conservatively")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--glossary-csv", required=True)
    parser.add_argument("--warnings-md", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    all_warnings: list[tuple[str, str]] = []
    all_terms: set[str] = set()

    for input_path in sorted(input_dir.glob("page_*.txt")):
        output_path = output_dir / input_path.name
        warnings, terms = clean_file(input_path, output_path)
        all_terms.update(terms)
        all_warnings.extend((input_path.name, warning) for warning in warnings)

    glossary_path = Path(args.glossary_csv)
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    with glossary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "reading", "zh", "type", "status", "note"])
        for term in sorted(all_terms):
            writer.writerow([term, "", "", "candidate", "pending_review", "auto-extracted"])

    warnings_path = Path(args.warnings_md)
    warnings_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# OCR Cleanup Warnings", ""]
    if all_warnings:
        for page, warning in all_warnings:
            lines.append(f"- `{page}`: {warning}")
    else:
        lines.append("- None")
    warnings_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

