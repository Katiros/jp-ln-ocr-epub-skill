#!/usr/bin/env python3
"""Translate a chapter text file with DeepSeek.

Input is plain UTF-8 Japanese text. Output is Markdown containing translation,
glossary updates, and OCR notes.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_ENDPOINT = "https://api.deepseek.com/chat/completions"


SYSTEM_PROMPT = """You are translating a Japanese vertical light novel into Simplified Chinese.
Preserve chapter structure, paragraph breaks, dialogue rhythm, names, honorific nuance, and glossary consistency.
The glossary is a translation reference, not a mechanical replacement table. If a glossary line is clearly not an independent term in the current context, ignore that line.
If the Japanese source appears corrupted by OCR, mark it as [OCR疑问: ...] and infer only when context is strong.
Return exactly these sections:
## Translation
## Glossary Updates
## OCR Notes
"""


def read_optional(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def call_deepseek(endpoint: str, api_key: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"DeepSeek HTTP error {exc.code}: {detail}") from exc
    return body["choices"][0]["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate OCR text with DeepSeek")
    parser.add_argument("--input", required=True, help="UTF-8 Japanese text file")
    parser.add_argument("--output", required=True, help="Markdown output path")
    parser.add_argument("--glossary", help="optional glossary YAML/Markdown path")
    parser.add_argument("--context", help="optional previous context or chapter summary path")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key env var: {args.api_key_env}")

    source = Path(args.input).read_text(encoding="utf-8")
    glossary = read_optional(args.glossary)
    context = read_optional(args.context)
    prompt = f"""# Glossary
{glossary}

# Previous Context
{context}

# Japanese OCR Source
{source}
"""
    result = call_deepseek(args.endpoint, api_key, args.model, prompt)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    print(f"Wrote translation: {output}")


if __name__ == "__main__":
    main()
