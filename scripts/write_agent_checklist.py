#!/usr/bin/env python3
"""Write a self-check checklist for agents running this skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CHECKS = [
    ("manifest", "00_manifest/manifest.json", "必须存在。记录输入页序、OCR 状态和断点信息。"),
    ("quality_report", "logs/quality_report.md", "OCR 后必须存在。用于人工检查低置信度页。"),
    ("ordered_jp", "03_ordered_jp", "OCR 后应包含 page_*.txt。"),
    ("cleaned_jp", "04_cleaned_jp", "clean 后应包含 page_*.txt，章节合并后应包含 chapter_*.jp.md。"),
    ("cleanup_warnings", "logs/cleanup_warnings.md", "clean 后必须存在。记录疑似 ruby/OCR 异常。"),
    ("ocr_ruby_candidates", "logs/ruby_candidates.csv", "OCR 后必须存在。记录已从正文流剥离的振假名候选。"),
    ("inline_ruby_review", "logs/ruby_inline_review.csv", "clean 后必须存在。记录文本内被剥离的振假名。"),
    ("glossary_candidates", "05_glossary/glossary_candidates.csv", "clean 后必须存在。原始术语候选。"),
    ("glossary_draft", "05_glossary/glossary_draft.csv", "draft-glossary 后应存在。人工复核初版。"),
    ("translation_glossary", "05_glossary/glossary_for_translation.txt", "build-translation-glossary 后应存在。DeepSeek 翻译优先使用它。"),
    ("chapter_boundaries", "00_manifest/chapter_boundaries.json", "detect-chapters 后应存在。"),
    ("review_readme", "08_review/README_REVIEW.md", "review-pack 后必须存在。人工复核入口。"),
    ("review_low_confidence", "08_review/low_confidence_pages.md", "review-pack 后必须存在。"),
    ("review_cleanup_warnings", "08_review/cleanup_warnings.md", "review-pack 后必须存在。"),
    ("review_ruby_candidates", "08_review/ruby_candidates.csv", "review-pack 后应存在。OCR 阶段振假名剥离复核。"),
    ("review_inline_ruby", "08_review/ruby_inline_review.csv", "review-pack 后应存在。文本内振假名剥离复核。"),
    ("review_glossary", "08_review/glossary_review.md", "review-pack 后必须存在。"),
    ("review_chapters", "08_review/chapter_boundaries_review.md", "review-pack 后必须存在。"),
    ("review_docx_index", "08_review/docx_review_index.md", "review-pack 后必须存在。"),
    ("output_readme", "README_OUTPUTS.md", "write-readme 后必须存在。解释输出目录用途。"),
    ("chapters_docx", "chapters", "export-docx 后应包含 ch*.docx。"),
]


def path_status(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    exists = path.exists()
    item: dict[str, Any] = {
        "path": relative,
        "exists": exists,
        "is_dir": path.is_dir() if exists else False,
        "file_count": 0,
        "size": 0,
    }
    if not exists:
        return item
    if path.is_dir():
        files = [child for child in path.rglob("*") if child.is_file()]
        item["file_count"] = len(files)
        item["size"] = sum(child.stat().st_size for child in files)
    else:
        item["file_count"] = 1
        item["size"] = path.stat().st_size
    return item


def status_label(item: dict[str, Any]) -> str:
    if not item["exists"]:
        return "MISSING"
    if item["file_count"] == 0 or item["size"] == 0:
        return "EMPTY"
    return "OK"


def build_checks(output_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for key, relative, description in CHECKS:
        item = path_status(output_dir, relative)
        item.update({"key": key, "description": description, "status": status_label(item)})
        rows.append(item)
    review_cleanup = output_dir / "08_review" / "cleanup_warnings.md"
    for row in rows:
        if row["key"] == "cleanup_warnings" and row["status"] == "MISSING" and review_cleanup.exists():
            row["status"] = "WARN"
            row["description"] += " 根目录日志缺失，但 08_review/cleanup_warnings.md 存在。"
    return rows


def write_markdown(output_dir: Path, rows: list[dict[str, Any]], path: Path) -> None:
    missing = [row for row in rows if row["status"] in {"MISSING", "EMPTY"}]
    warnings = [row for row in rows if row["status"] == "WARN"]
    lines = [
        "# Agent Self-Check Checklist",
        "",
        "这个文件给 Codex/OpenClaw 自查用。结束任务前必须确认 review 文件和关键阶段产物不是漏生成状态。",
        "",
        f"- Output dir: `{output_dir}`",
        f"- Missing/empty checks: `{len(missing)}`",
        f"- Warnings: `{len(warnings)}`",
        "",
        "## 必须处理的问题",
        "",
    ]
    if not missing:
        lines.append("- 无。")
    else:
        for row in missing:
            lines.append(f"- [{row['status']}] `{row['path']}`：{row['description']}")
    if warnings:
        lines.extend(["", "## 警告", ""])
        for row in warnings:
            lines.append(f"- [WARN] `{row['path']}`：{row['description']}")

    lines.extend(["", "## 全量检查", "", "| 状态 | 路径 | 文件数 | 大小 | 说明 |", "|---|---|---:|---:|---|"])
    for row in rows:
        lines.append(
            f"| {row['status']} | `{row['path']}` | {row['file_count']} | {row['size']} | {row['description']} |"
        )

    lines.extend(
        [
            "",
            "## Agent 结束前要求",
            "",
            "- 如果 `08_review/README_REVIEW.md` 缺失，必须先运行 `review-pack`。",
            "- 如果 `README_OUTPUTS.md` 缺失，必须先运行 `write-readme`。",
            "- 如果 `glossary_for_translation.txt` 缺失，翻译前必须先运行 `build-translation-glossary`。",
            "- 如果 `chapters/` 没有 Word 文件，不要声称已经生成 Word 审阅稿。",
            "- 如果 `06_translated_zh/` 为空，不要声称已经完成翻译。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write agent self-check checklist")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_checks(output_dir)
    write_markdown(output_dir, rows, output_dir / "AGENT_CHECKLIST.md")
    (output_dir / "AGENT_CHECKLIST.json").write_text(
        json.dumps({"output_dir": str(output_dir), "checks": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output_dir / "AGENT_CHECKLIST.md")


if __name__ == "__main__":
    main()
