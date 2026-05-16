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
INLINE_RUBY_BETWEEN_KANJI = re.compile(r"(?<=[一-龯々])([ぁ-ゖァ-ヴー]{2,8})(?=[一-龯々])")
INLINE_ONE_KANA_BEFORE_PARTICLE = re.compile(r"(?<=[一-龯々])([ぁ-ゖァ-ヴー])([のはがをにへとでもや])(?=[一-龯々])")
PARTICLE_LIKE = set("のはがをにへとでもや")


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


def strip_inline_ruby(line: str) -> tuple[str, list[str]]:
    """Conservatively remove OCR-inline furigana from a single text line.

    This handles cases like 上かみ条じょう当とう麻ま by removing kana runs
    that sit between kanji. It intentionally avoids one-kana okurigana such
    as 引き返す or 持ち込む, and avoids trailing kana because that is too
    easy to confuse with normal grammar particles.
    """

    removed: list[str] = []

    def between_repl(match: re.Match[str]) -> str:
        text = match.group(1)
        if text[-1] in PARTICLE_LIKE:
            return text
        removed.append(text)
        return ""

    cleaned = INLINE_RUBY_BETWEEN_KANJI.sub(between_repl, line)
    if removed:
        def one_kana_repl(match: re.Match[str]) -> str:
            removed.append(match.group(1))
            return match.group(2)

        cleaned = INLINE_ONE_KANA_BEFORE_PARTICLE.sub(one_kana_repl, cleaned)
    return cleaned, removed


def cleanup_lines(lines: list[str], page_name: str = "") -> tuple[list[str], list[str], set[str], list[dict[str, str]]]:
    cleaned: list[str] = []
    warnings: list[str] = []
    glossary: set[str] = set()
    ruby_rows: list[dict[str, str]] = []
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
        stripped_line, removed_ruby = strip_inline_ruby(line)
        if removed_ruby and stripped_line != line:
            ruby_rows.append(
                {
                    "page": page_name,
                    "original": line,
                    "cleaned": stripped_line,
                    "removed": " ".join(removed_ruby),
                    "reason": "inline kana between kanji treated as ruby",
                }
            )
            warnings.append(f"Removed inline ruby: {line} -> {stripped_line} ({' '.join(removed_ruby)})")
            line = stripped_line
        if RUBY_CONTAMINATION.search(line):
            warnings.append(f"Possible ruby contamination: {line}")
        for term in KATAKANA_TERM.findall(line):
            glossary.add(term)
        for term in KANJI_NAME.findall(line):
            if len(term) >= 3:
                glossary.add(term)
        cleaned.append(line)
    return cleaned, warnings, glossary, ruby_rows


def clean_file(input_path: Path, output_path: Path) -> tuple[list[str], set[str], list[dict[str, str]]]:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    cleaned, warnings, glossary, ruby_rows = cleanup_lines(lines, input_path.name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(cleaned).strip() + "\n", encoding="utf-8")
    return warnings, glossary, ruby_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean ordered Japanese OCR text conservatively")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--glossary-csv", required=True)
    parser.add_argument("--warnings-md", required=True)
    parser.add_argument("--ruby-review-csv")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    all_warnings: list[tuple[str, str]] = []
    all_terms: set[str] = set()
    all_ruby_rows: list[dict[str, str]] = []

    for input_path in sorted(input_dir.glob("page_*.txt")):
        output_path = output_dir / input_path.name
        warnings, terms, ruby_rows = clean_file(input_path, output_path)
        all_terms.update(terms)
        all_ruby_rows.extend(ruby_rows)
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

    ruby_review_path = Path(args.ruby_review_csv) if args.ruby_review_csv else warnings_path.parent / "ruby_inline_review.csv"
    ruby_review_path.parent.mkdir(parents=True, exist_ok=True)
    with ruby_review_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["page", "original", "cleaned", "removed", "reason"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_ruby_rows)


if __name__ == "__main__":
    main()
