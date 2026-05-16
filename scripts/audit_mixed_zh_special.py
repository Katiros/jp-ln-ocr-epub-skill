#!/usr/bin/env python3
"""Find glossary rows whose Chinese translation mixes Han text and Latin text.

These are often special ruby / gikun candidates, e.g.
  原子崩しメルトダウナー -> 原子崩坏Meltdowner
should probably become
  <ruby>原子崩し<rt>メルトダウナー</rt></ruby>
  <ruby>原子崩坏<rt>Meltdowner</rt></ruby>
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


HAN = r"\u4e00-\u9fff"
HAS_HAN_LATIN = re.compile(rf"[{HAN}].*[A-Za-z]|[A-Za-z].*[{HAN}]")
JP_KATA_TAIL = re.compile(rf"^(.+?[{HAN}ぁ-ゖ].*?)([ァ-ヴー][ァ-ヴー・=\sA-Za-z0-9._'-]*)$")
JP_LATIN_TAIL = re.compile(rf"^(.+?[{HAN}ぁ-ゖ].*?)([A-Za-z][A-Za-z0-9 ._'-]*)$")
ZH_LATIN_TAIL = re.compile(rf"^(.+?[{HAN}].*?)([A-Za-z][A-Za-z0-9 ._'-]*)$")
FIELDS = [
    "csv_line",
    "source",
    "zh",
    "type",
    "ruby_mode",
    "raw_source",
    "suggested_ruby_mode",
    "suggested_source",
    "suggested_reading",
    "suggested_rich_source",
    "suggested_rich_zh",
    "confidence",
    "reason",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def ruby_html(base: str, reading: str) -> str:
    return f"<ruby>{base}<rt>{reading}</rt></ruby>" if base and reading else ""


def split_source(source: str) -> tuple[str, str, str]:
    match = JP_KATA_TAIL.match(source)
    if match:
        return clean(match.group(1)), clean(match.group(2)), "jp_katakana_tail"
    match = JP_LATIN_TAIL.match(source)
    if match:
        return clean(match.group(1)), clean(match.group(2)), "jp_latin_tail"
    return "", "", ""


def split_zh(zh: str) -> tuple[str, str]:
    match = ZH_LATIN_TAIL.match(zh)
    if match:
        return clean(match.group(1)), clean(match.group(2))
    return "", ""


def classify(row: dict[str, str]) -> dict[str, str] | None:
    source = clean(row.get("source"))
    zh = clean(row.get("zh"))
    ruby_mode = clean(row.get("ruby_mode"))
    if ruby_mode == "special" or not HAS_HAN_LATIN.search(zh):
        return None

    jp_base, jp_rt, jp_reason = split_source(source)
    zh_base, zh_rt = split_zh(zh)
    if not jp_base or not jp_rt or not zh_base or not zh_rt:
        return None

    confidence = "high"
    reason = f"{jp_reason}; zh has Han+Latin tail"
    if re.match(r"^[A-Z0-9&:・. -]+", source):
        confidence = "medium"
        reason += "; source begins with Latin/acronym, verify manually"
    if clean(row.get("type")) in {"科技", "科技/装备", "地名/企业"}:
        confidence = "medium"
        reason += "; type may be ordinary mixed brand/tech term"

    return {
        "source": source,
        "zh": zh,
        "type": clean(row.get("type")),
        "ruby_mode": ruby_mode,
        "raw_source": clean(row.get("raw_source")),
        "suggested_ruby_mode": "special",
        "suggested_source": jp_base,
        "suggested_reading": jp_rt,
        "suggested_rich_source": ruby_html(jp_base, jp_rt),
        "suggested_rich_zh": ruby_html(zh_base, zh_rt),
        "confidence": confidence,
        "reason": reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit mixed Chinese/English zh terms as possible special ruby")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidates: list[dict[str, str]] = []
    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as f:
        for csv_line, row in enumerate(csv.DictReader(f), start=2):
            item = classify({key: clean(value) for key, value in row.items()})
            if item:
                item["csv_line"] = str(csv_line)
                candidates.append(item)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(candidates)
    print(f"Wrote {len(candidates)} possible special ruby rows: {output}")


if __name__ == "__main__":
    main()
