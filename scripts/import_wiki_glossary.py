#!/usr/bin/env python3
"""Import glossary candidates from a MediaWiki-compatible wiki.

Designed for Toaru HuijiWiki, but works with other MediaWiki API endpoints.
It reads OCR glossary candidates or a seed list, searches the wiki, fetches
matching pages, extracts likely Japanese names/readings/Chinese titles, and
writes a reviewable CSV. It never overwrites confirmed glossary entries.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://toaru.huijiwiki.com/api.php"
DEFAULT_PAGE_URL = "https://toaru.huijiwiki.com/wiki/{title}"
USER_AGENT = "jp-ln-ocr-epub-skill/0.1 (+https://github.com/Katiros/jp-ln-ocr-epub-skill)"

FIELD_PATTERNS = {
    "ja": re.compile(r"(?:日文名|日语名|日文|原文名|原名)\s*[=:：]\s*([^\n|<>{}]+)"),
    "reading": re.compile(r"(?:假名|读音|讀音|平假名|日文读音|日文讀音)\s*[=:：]\s*([ぁ-ゖァ-ヴー・=\s]+)"),
    "zh": re.compile(r"(?:中文名|简中名|簡中名|译名|譯名|名称)\s*[=:：]\s*([^\n|<>{}]+)"),
}
WIKI_MARKUP = re.compile(r"'''|\[\[|\]\]|\{\{|\}\}|<[^>]+>")


def http_get_json(url: str, params: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = WIKI_MARKUP.sub("", value)
    value = value.replace("&nbsp;", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -\t\r\n")


def read_seed_terms(path: Path | None, limit: int) -> list[str]:
    if path is None or not path.exists():
        return []
    terms: list[str] = []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                term = (row.get("source") or row.get("term") or "").strip()
                status = (row.get("status") or "").strip()
                if term and status != "confirmed":
                    terms.append(term)
    else:
        terms = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    deduped = []
    seen = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            deduped.append(term)
        if limit and len(deduped) >= limit:
            break
    return deduped


def read_manual_glossary(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = (row.get("source") or row.get("ja") or row.get("日文") or row.get("原文") or "").strip()
            zh = (row.get("zh") or row.get("中文") or row.get("译名") or row.get("譯名") or "").strip()
            reading = (row.get("reading") or row.get("读音") or row.get("假名") or "").strip()
            if not source and not zh:
                continue
            rows.append(
                {
                    "source": source or zh,
                    "reading": reading,
                    "zh": zh,
                    "type": row.get("type") or "manual_wiki_candidate",
                    "status": row.get("status") or "pending_review",
                    "note": row.get("note") or f"imported from manual file: {path.name}",
                    "wiki_title": row.get("wiki_title") or zh or source,
                    "wiki_url": row.get("wiki_url") or "",
                    "ja": row.get("ja") or source,
                }
            )
    return rows


def make_manual_row(path: Path, source: str, zh: str, reading: str = "", note: str = "") -> dict[str, str]:
    source = clean_text(source)
    zh = clean_text(zh)
    reading = clean_text(reading)
    title = zh or source
    return {
        "source": source or zh,
        "reading": reading,
        "zh": zh,
        "type": "manual_wiki_candidate",
        "status": "pending_review",
        "note": note or f"imported from manual text: {path.name}",
        "wiki_title": title,
        "wiki_url": "",
        "ja": source,
    }


def read_manual_text_glossary(path: Path | None) -> list[dict[str, str]]:
    """Read glossary rows from browser-copied wiki text/HTML/Markdown.

    Supported loose formats:
    - labeled fields: 日文名：... / 中文名：... / 假名：...
    - table-like lines: source<TAB>zh<TAB>reading, source|zh|reading
    - simple mappings: source => zh, source = zh
    """

    if path is None or not path.exists():
        return []
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = html.unescape(raw)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(?:p|tr|li|div|h\d)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [clean_text(line) for line in text.splitlines()]
    rows: list[dict[str, str]] = []

    for block in re.split(r"\n\s*\n+", text):
        fields = extract_fields("", block)
        if fields.get("ja") or fields.get("zh") or fields.get("reading"):
            rows.append(
                make_manual_row(
                    path,
                    fields.get("ja") or fields.get("zh") or "",
                    fields.get("zh") or fields.get("ja") or "",
                    fields.get("reading", ""),
                    "matched labeled wiki fields",
                )
            )

    for line in lines:
        if not line or line.startswith(("#", "目录", "导航")):
            continue
        if re.search(r"(日文名|中文名|简中名|假名|读音|譯名|译名)\s*[=:：]", line):
            fields = extract_fields("", line)
            if fields.get("ja") or fields.get("zh"):
                rows.append(
                    make_manual_row(
                        path,
                        fields.get("ja") or fields.get("zh") or "",
                        fields.get("zh") or fields.get("ja") or "",
                        fields.get("reading", ""),
                        "matched labeled wiki line",
                    )
                )
            continue

        if "\t" in line or "|" in line:
            parts = [clean_text(part) for part in re.split(r"\t+|\s*\|\s*", line) if clean_text(part)]
            if len(parts) >= 2 and not any(part in {"日文", "中文", "假名", "原文", "译名"} for part in parts[:2]):
                reading = next((part for part in parts[2:] if re.fullmatch(r"[ぁ-ゖァ-ヴー・=\s]+", part)), "")
                rows.append(make_manual_row(path, parts[0], parts[1], reading, "matched table-like wiki line"))
            continue

        match = re.match(r"(.{1,80}?)(?:\s*=>\s*|\s*[=＝:：]\s*)(.{1,80})$", line)
        if match and not re.search(r"https?://", line):
            rows.append(make_manual_row(path, match.group(1), match.group(2), "", "matched manual mapping line"))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row["source"], row["zh"], row["reading"])
        if row["source"] and key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def search_pages(api_url: str, term: str, per_term: int) -> list[str]:
    data = http_get_json(
        api_url,
        {
            "action": "query",
            "list": "search",
            "srsearch": term,
            "srlimit": per_term,
            "format": "json",
            "formatversion": "2",
        },
    )
    return [item["title"] for item in data.get("query", {}).get("search", []) if "title" in item]


def fetch_wikitext(api_url: str, title: str) -> str:
    data = http_get_json(
        api_url,
        {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        },
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return ""
    revisions = pages[0].get("revisions", [])
    if not revisions:
        return ""
    rev = revisions[0]
    slots = rev.get("slots", {})
    if isinstance(slots, dict) and "main" in slots:
        return slots["main"].get("content", "")
    return rev.get("content", "")


def extract_fields(title: str, wikitext: str) -> dict[str, str]:
    result = {"wiki_title": clean_text(title), "ja": "", "reading": "", "zh": clean_text(title)}
    text = clean_text(wikitext)
    raw = wikitext.replace("\r\n", "\n")
    for key, pattern in FIELD_PATTERNS.items():
        match = pattern.search(raw) or pattern.search(text)
        if match:
            result[key] = clean_text(match.group(1))
    if not result["ja"]:
        ja_match = re.search(r"([一-龯々ァ-ヴー・＝=]{2,})[（(]([ぁ-ゖァ-ヴー\s]+)[）)]", text)
        if ja_match:
            result["ja"] = clean_text(ja_match.group(1))
            result["reading"] = clean_text(ja_match.group(2))
    return result


def import_terms(api_url: str, page_url: str, terms: list[str], per_term: int, sleep: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_pages = set()
    for term in terms:
        try:
            titles = search_pages(api_url, term, per_term)
        except Exception as exc:
            rows.append(error_row(term, "", f"search failed: {exc}", page_url))
            continue
        for title in titles:
            if title in seen_pages:
                continue
            seen_pages.add(title)
            try:
                wikitext = fetch_wikitext(api_url, title)
                fields = extract_fields(title, wikitext)
                encoded_title = urllib.parse.quote(title.replace(" ", "_"))
                rows.append(
                    {
                        "source": fields.get("ja") or term,
                        "reading": fields.get("reading", ""),
                        "zh": fields.get("zh") or fields.get("wiki_title") or title,
                        "type": "wiki_candidate",
                        "status": "pending_review",
                        "note": f"matched from seed: {term}",
                        "wiki_title": fields.get("wiki_title") or title,
                        "wiki_url": page_url.format(title=encoded_title),
                        "ja": fields.get("ja", ""),
                    }
                )
            except Exception as exc:
                rows.append(error_row(term, title, f"fetch failed: {exc}", page_url))
            if sleep:
                time.sleep(sleep)
    return rows


def error_row(term: str, title: str, note: str, page_url: str) -> dict[str, str]:
    encoded_title = urllib.parse.quote(title.replace(" ", "_")) if title else ""
    return {
        "source": term,
        "reading": "",
        "zh": "",
        "type": "wiki_candidate",
        "status": "api_error",
        "note": note,
        "wiki_title": title,
        "wiki_url": page_url.format(title=encoded_title) if encoded_title else "",
        "ja": "",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source", "reading", "zh", "type", "status", "note", "wiki_title", "wiki_url", "ja"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import glossary candidates from a MediaWiki wiki")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL)
    parser.add_argument("--terms-csv", help="Existing glossary_candidates.csv")
    parser.add_argument("--seed-file", help="Plain text seed terms, one per line")
    parser.add_argument("--manual-csv", help="Manually exported wiki glossary CSV to merge without API access")
    parser.add_argument("--manual-text", help="Browser-saved/copied wiki text, Markdown, or HTML to parse without API access")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--per-term", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()

    manual_rows = read_manual_glossary(Path(args.manual_csv) if args.manual_csv else None)
    manual_rows += read_manual_text_glossary(Path(args.manual_text) if args.manual_text else None)
    terms = read_seed_terms(Path(args.terms_csv) if args.terms_csv else None, args.limit)
    extra_terms = read_seed_terms(Path(args.seed_file) if args.seed_file else None, args.limit)
    for term in extra_terms:
        if term not in terms:
            terms.append(term)
    if args.limit:
        terms = terms[: args.limit]
    if not terms and not manual_rows:
        raise SystemExit("No seed terms found. Provide --terms-csv or --seed-file.")
    rows = manual_rows + (import_terms(args.api_url, args.page_url, terms, args.per_term, args.sleep) if terms else [])
    write_csv(Path(args.output), rows)
    print(f"Wrote {len(rows)} wiki glossary candidates: {args.output}")


if __name__ == "__main__":
    main()
