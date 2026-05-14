#!/usr/bin/env python3
"""Detect chapter boundaries from ordered/cleaned Japanese OCR page text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CHAPTER_PATTERNS = [
    re.compile(r"(序章|終章|第[一二三四五六七八九十]+章).{0,30}"),
]


def detect_pages(input_dir: Path) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("page_*.txt")):
        text = path.read_text(encoding="utf-8")
        page_match = re.search(r"page_(\d+)", path.stem)
        page = int(page_match.group(1)) if page_match else None
        for pattern in CHAPTER_PATTERNS:
            for match in pattern.finditer(text.replace("\n", "")):
                hits.append(
                    {
                        "page": page,
                        "file": path.name,
                        "marker": match.group(1),
                        "snippet": match.group(0),
                    }
                )
    return hits


def build_ranges(hits: list[dict[str, object]]) -> list[dict[str, object]]:
    ranges: list[dict[str, object]] = []
    sorted_hits = sorted(hits, key=lambda item: int(item["page"]))
    for i, hit in enumerate(sorted_hits):
        start = int(hit["page"])
        next_start = int(sorted_hits[i + 1]["page"]) if i + 1 < len(sorted_hits) else None
        ranges.append(
            {
                "marker": hit["marker"],
                "title_snippet": hit["snippet"],
                "start_page": start,
                "end_page_exclusive": next_start,
                "end_page_inclusive": next_start - 1 if next_start else None,
            }
        )
    return ranges


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect chapter boundaries from OCR text")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    hits = detect_pages(Path(args.input_dir))
    data = {"chapter_hits": hits, "ranges": build_ranges(hits)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

