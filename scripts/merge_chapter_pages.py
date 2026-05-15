#!/usr/bin/env python3
"""Merge cleaned page text into chapter Markdown files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PAGE_RE = re.compile(r"page_(\d+)\.txt$")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def page_number(path: Path) -> int:
    match = PAGE_RE.search(path.name)
    if not match:
        raise ValueError(f"Not a page text file: {path}")
    return int(match.group(1))


def available_pages(input_dir: Path) -> list[int]:
    pages: list[int] = []
    for path in input_dir.glob("page_*.txt"):
        try:
            pages.append(page_number(path))
        except ValueError:
            continue
    return sorted(pages)


def build_ranges(boundaries: dict[str, Any], pages: list[int]) -> list[dict[str, Any]]:
    explicit = boundaries.get("ranges") if isinstance(boundaries, dict) else None
    if explicit:
        ranges = []
        max_page = max(pages) if pages else None
        for index, item in enumerate(explicit, start=1):
            start = int(item["start_page"])
            end = item.get("end_page_inclusive")
            if end is None:
                end = max_page
            ranges.append(
                {
                    "index": index,
                    "title": item.get("title_snippet") or item.get("marker") or f"Chapter {index}",
                    "start_page": start,
                    "end_page": int(end) if end is not None else start,
                }
            )
        return ranges

    if not pages:
        return []
    return [{"index": 1, "title": "Chapter 1", "start_page": pages[0], "end_page": pages[-1]}]


def merge_one(input_dir: Path, output_dir: Path, chapter: dict[str, Any]) -> Path:
    chapter_index = int(chapter["index"])
    start = int(chapter["start_page"])
    end = int(chapter["end_page"])
    title = str(chapter.get("title") or f"Chapter {chapter_index}")
    lines = [f"# {title}", ""]

    for page in range(start, end + 1):
        path = input_dir / f"page_{page:04d}.txt"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        lines.append(f"<!-- page {page:04d} -->")
        lines.append("")
        lines.append(text)
        lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"chapter_{chapter_index:02d}.jp.md"
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge cleaned OCR page text into chapter Markdown")
    parser.add_argument("--input-dir", required=True, help="Directory containing 04_cleaned_jp/page_*.txt")
    parser.add_argument("--boundaries", required=True, help="00_manifest/chapter_boundaries.json")
    parser.add_argument("--output-dir", required=True, help="Usually 04_cleaned_jp")
    parser.add_argument("--chapter", type=int, default=0, help="Only merge this 1-based chapter index")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    pages = available_pages(input_dir)
    ranges = build_ranges(read_json(Path(args.boundaries)), pages)
    if args.chapter:
        ranges = [item for item in ranges if int(item["index"]) == args.chapter]
    if not ranges:
        raise SystemExit("No chapter ranges found and no page text files are available.")

    for chapter in ranges:
        print(merge_one(input_dir, output_dir, chapter))


if __name__ == "__main__":
    main()
