#!/usr/bin/env python3
"""Build a first-pass reviewable glossary from OCR/wiki candidates.

The output is intentionally a draft. It reduces manual blank filling, but keeps
all rows reviewable and never marks generated translations as confirmed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


FIELDS = ["source", "reading", "zh", "type", "status", "confidence", "source_hint", "note"]
KATAKANA = re.compile(r"^[ァ-ヴー・＝=]+$")
KANJIISH = re.compile(r"^[一-龯々ヶのノ・＝=]+$")
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"


def clean(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def key_variants(value: str) -> set[str]:
    value = clean(value)
    if not value:
        return set()
    return {
        value,
        value.replace("=", "＝"),
        value.replace("＝", "="),
        value.replace("・", ""),
        value.replace("＝", "").replace("=", ""),
    }


def build_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        for field in ("source", "ja", "wiki_title", "term"):
            for key in key_variants(row.get(field, "")):
                if key and key not in lookup:
                    lookup[key] = row
    return lookup


def infer_type(source: str) -> str:
    if KATAKANA.fullmatch(source):
        return "katakana_name_or_term"
    if KANJIISH.fullmatch(source):
        return "name_or_term"
    return "candidate"


def deterministic_draft(source: str) -> tuple[str, str, str, str]:
    if KANJIISH.fullmatch(source) and len(source) <= 8:
        return source, "draft", "medium", "kanji copied as Chinese draft"
    if "魔神" in source:
        return source, "draft", "medium", "contains shared CJK term"
    return "", "pending_review", "low", "needs translation draft"


def merge_rows(candidates: list[dict[str, str]], wiki_rows: list[dict[str, str]], seed_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    wiki_lookup = build_lookup(wiki_rows)
    seed_lookup = build_lookup(seed_rows)
    merged: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in candidates + seed_rows + wiki_rows:
        source = clean(row.get("source") or row.get("ja") or row.get("term"))
        if not source or source in seen:
            continue
        seen.add(source)

        seed = next((seed_lookup[key] for key in key_variants(source) if key in seed_lookup), {})
        wiki = next((wiki_lookup[key] for key in key_variants(source) if key in wiki_lookup), {})
        source_row = seed or wiki or row
        zh = clean(source_row.get("zh") or source_row.get("中文") or source_row.get("译名"))
        reading = clean(source_row.get("reading") or source_row.get("假名") or row.get("reading"))

        if zh:
            status = "draft"
            confidence = "high" if seed else "medium"
            source_hint = "seed_glossary" if seed else "wiki_candidate"
            note = clean(source_row.get("note")) or "prefilled from existing glossary/wiki candidate"
        else:
            zh, status, confidence, note = deterministic_draft(source)
            source_hint = "heuristic"

        merged.append(
            {
                "source": source,
                "reading": reading,
                "zh": zh,
                "type": clean(source_row.get("type")) or infer_type(source),
                "status": status,
                "confidence": confidence,
                "source_hint": source_hint,
                "note": note,
            }
        )
    return merged


def deepseek_fill(rows: list[dict[str, str]], api_key: str, base_url: str, model: str, batch_size: int) -> None:
    missing = [row for row in rows if not row["zh"]]
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        payload_rows = [{"source": row["source"], "reading": row["reading"], "type": row["type"]} for row in batch]
        prompt = (
            "你是日文轻小说术语表助手。请为术语候选生成简体中文译名草案。\n"
            "要求：只输出 JSON 数组；每项包含 source, zh, type, note。"
            "人名/专名尽量使用中文轻小说译名风格；不确定时保守音译并在 note 写待确认。\n\n"
            f"候选：\n{json.dumps(payload_rows, ensure_ascii=False)}"
        )
        response = chat_completion(api_key, base_url, model, prompt)
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", response)
            data = json.loads(match.group(0)) if match else []
        by_source = {clean(item.get("source")): item for item in data if isinstance(item, dict)}
        for row in batch:
            item = by_source.get(row["source"])
            if not item:
                continue
            zh = clean(item.get("zh"))
            if zh:
                row["zh"] = zh
                row["type"] = clean(item.get("type")) or row["type"]
                row["status"] = "draft"
                row["confidence"] = "low"
                row["source_hint"] = "deepseek_draft"
                row["note"] = clean(item.get("note")) or "generated by DeepSeek, needs review"
        time.sleep(0.2)


def chat_completion(api_key: str, base_url: str, model: str, prompt: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出合法 JSON，不要输出解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a draft glossary for human review")
    parser.add_argument("--candidates-csv", required=True)
    parser.add_argument("--wiki-csv")
    parser.add_argument("--seed-csv", help="Existing confirmed/manual glossary CSV")
    parser.add_argument("--output", required=True)
    parser.add_argument("--deepseek", action="store_true", help="Use DeepSeek to draft missing zh values")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=40)
    args = parser.parse_args()

    rows = merge_rows(
        read_csv(Path(args.candidates_csv)),
        read_csv(Path(args.wiki_csv) if args.wiki_csv else None),
        read_csv(Path(args.seed_csv) if args.seed_csv else None),
    )
    if args.deepseek:
        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise SystemExit(f"{args.api_key_env} is not set.")
        deepseek_fill(rows, api_key, args.base_url, args.model, args.batch_size)
    write_csv(Path(args.output), rows)
    print(f"Wrote {len(rows)} draft glossary rows: {args.output}")


if __name__ == "__main__":
    main()
