#!/usr/bin/env python3
"""Build a Chinese human-review pack under 08_review/."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def write_low_confidence(output_dir: Path, review_dir: Path, threshold: float) -> None:
    manifest = read_json(output_dir / "00_manifest" / "manifest.json")
    lines = ["# 低置信度与异常页面", ""]
    if not manifest:
        lines.append("- 未找到 `00_manifest/manifest.json`。")
        (review_dir / "low_confidence_pages.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    pages = manifest.get("pages", [])
    low_pages = []
    error_pages = []
    review_pages = []
    for page in pages:
        conf = page.get("mean_confidence")
        status = page.get("ocr_status")
        kind = page.get("kind")
        if isinstance(conf, (int, float)) and conf < threshold:
            low_pages.append(page)
        if status == "error":
            error_pages.append(page)
        if kind in {"unknown", "chapter", "toc", "copyright"}:
            review_pages.append(page)

    lines.append(f"- OCR 置信度阈值：`{threshold}`")
    lines.append(f"- 低置信度页面数：`{len(low_pages)}`")
    lines.append(f"- OCR 错误页面数：`{len(error_pages)}`")
    lines.append(f"- 建议复核页面数：`{len(review_pages)}`")
    lines.append("")

    def add_pages(title: str, items: list[dict[str, Any]]) -> None:
        lines.append(f"## {title}")
        if not items:
            lines.append("- 无")
            lines.append("")
            return
        for page in items:
            index = int(page.get("index", 0))
            ordered = page.get("ordered_jp", "")
            target = f"../03_ordered_jp/page_{index:04d}.txt"
            lines.append(
                f"- page `{index:04d}` | type=`{page.get('kind')}` | "
                f"status=`{page.get('ocr_status')}` | conf=`{page.get('mean_confidence')}` | "
                f"[查看 OCR 文本]({target}) | `{page.get('file')}`"
            )
            if ordered and not Path(str(ordered)).exists():
                lines.append(f"  - manifest 记录的文本路径不存在：`{ordered}`")
        lines.append("")

    add_pages("低置信度页面", low_pages)
    add_pages("OCR 错误页面", error_pages)
    add_pages("页面类型建议复核", review_pages)
    (review_dir / "low_confidence_pages.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_chapter_summary(output_dir: Path, review_dir: Path) -> None:
    data = read_json(output_dir / "00_manifest" / "chapter_boundaries.json")
    lines = ["# 章节边界复核", ""]
    if not data:
        lines.append("- 未找到 `00_manifest/chapter_boundaries.json`。请先运行章节检测。")
    else:
        ranges = data.get("ranges", [])
        if not ranges:
            lines.append("- 没有检测到章节边界。")
        for item in ranges:
            lines.append(
                f"- `{item.get('marker')}`：page `{item.get('start_page')}`"
                f" 到 `{item.get('end_page_inclusive')}`；标题片段：`{item.get('title_snippet')}`"
            )
    (review_dir / "chapter_boundaries_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_glossary_review(output_dir: Path, review_dir: Path) -> None:
    src = output_dir / "05_glossary" / "glossary_candidates.csv"
    dst = review_dir / "glossary_candidates.csv"
    copied = copy_if_exists(src, dst)
    wiki_src = output_dir / "05_glossary" / "wiki_glossary_candidates.csv"
    wiki_dst = review_dir / "wiki_glossary_candidates.csv"
    wiki_copied = copy_if_exists(wiki_src, wiki_dst)
    draft_src = output_dir / "05_glossary" / "glossary_draft.csv"
    draft_dst = review_dir / "glossary_draft.csv"
    draft_copied = copy_if_exists(draft_src, draft_dst)
    translation_src = output_dir / "05_glossary" / "glossary_for_translation.txt"
    translation_dst = review_dir / "glossary_for_translation.txt"
    translation_copied = copy_if_exists(translation_src, translation_dst)
    rejected_src = output_dir / "05_glossary" / "glossary_for_translation_rejected.csv"
    rejected_dst = review_dir / "glossary_for_translation_rejected.csv"
    rejected_copied = copy_if_exists(rejected_src, rejected_dst)
    lines = ["# 术语表复核", ""]
    if not copied:
        lines.append("- 未找到 `05_glossary/glossary_candidates.csv`。")
    else:
        count = 0
        with dst.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for _ in reader:
                count += 1
        lines.append(f"- 已复制术语候选：`{count}` 条。")
        lines.append("- 请确认人名、组织名、魔法/术式名和固定译名。")
        lines.append("- 确认后可把 `status` 改为 `confirmed`，并填写 `zh`。")
    if wiki_copied:
        lines.append("- 已复制 wiki 预填充术语候选：`wiki_glossary_candidates.csv`。")
        lines.append("- wiki 候选仍需人工确认，不会直接覆盖最终术语表。")
    if draft_copied:
        lines.append("- 已生成初版术语表：`glossary_draft.csv`。")
        lines.append("- 请优先复核这一份：修改 `zh`，把确认项的 `status` 改为 `confirmed`。")
    if translation_copied:
        lines.append("- 已生成翻译用术语表：`glossary_for_translation.txt`。")
        lines.append("- DeepSeek 翻译时请优先使用这份过滤后的术语表。")
    if rejected_copied:
        lines.append("- 已生成过滤明细：`glossary_for_translation_rejected.csv`，可查看哪些碎片没有进入翻译。")
    (review_dir / "glossary_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docx_index(output_dir: Path, review_dir: Path) -> None:
    lines = ["# Word 审阅文件索引", ""]
    chapters = output_dir / "chapters"
    files = sorted(chapters.glob("*.docx")) if chapters.exists() else []
    if not files:
        lines.append("- 未找到 Word 审阅文件。请先运行 `export_docx_chapter.py`。")
    else:
        for file in files:
            lines.append(f"- [{file.name}](../chapters/{file.name})")
    (review_dir / "docx_review_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(output_dir: Path, review_dir: Path) -> None:
    files = [
        ("low_confidence_pages.md", "低置信度、OCR 错误和建议复核页面。"),
        ("cleanup_warnings.md", "疑似 ruby 混入、异常 OCR 行等清洗警告。"),
        ("glossary_candidates.csv", "自动抽取的人名/术语候选，需要人工确认。"),
        ("wiki_glossary_candidates.csv", "从 wiki 预填充的人名/术语候选，需要人工确认。"),
        ("glossary_draft.csv", "已自动填入译名草案的初版术语表，优先复核这份。"),
        ("glossary_for_translation.txt", "过滤后的翻译用术语表，给 DeepSeek prompt 使用。"),
        ("glossary_for_translation_rejected.csv", "未进入翻译术语表的条目与原因。"),
        ("glossary_review.md", "术语表复核说明。"),
        ("chapter_boundaries_review.md", "章节边界检测结果的中文摘要。"),
        ("docx_review_index.md", "Word 审阅文件索引。"),
        ("quality_report.md", "OCR 质量报告原始副本。"),
    ]
    lines = [
        "# 人工复核中心",
        "",
        "这个目录汇总了需要人工看的材料。正常审阅时，优先打开这里，而不是在各阶段目录里到处找。",
        "",
        "## 建议审阅顺序",
        "",
        "1. 打开 `low_confidence_pages.md`，先看低置信度和异常页面。",
        "2. 打开 `cleanup_warnings.md`，检查疑似 ruby 混入和异常 OCR 行。",
        "3. 打开 `chapter_boundaries_review.md`，确认章节边界是否正确。",
        "4. 如果存在 `glossary_draft.csv`，优先复核这份初版术语表。",
        "5. 如需追溯来源，再打开 `glossary_candidates.csv` 和 `wiki_glossary_candidates.csv`。",
        "6. 打开 `docx_review_index.md`，进入 Word 文件校对 OCR 或译文。",
        "",
        "## 文件说明",
        "",
    ]
    for name, desc in files:
        exists = "存在" if (review_dir / name).exists() else "未生成"
        lines.append(f"- `{name}`：{desc}（{exists}）")
    lines.extend(
        [
            "",
            "## 注意",
            "",
            "- `08_review/` 是汇总入口，不是唯一数据源。",
            "- 原始 OCR JSON 仍在 `02_ocr_raw/`。",
            "- 每页排序后的日文仍在 `03_ordered_jp/`。",
            "- 清洗后的日文和章节稿仍在 `04_cleaned_jp/`。",
            "- Word 文件仍在 `chapters/`。",
        ]
    )
    (review_dir / "README_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 08_review human-review pack")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--confidence-threshold", type=float, default=0.82)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    review_dir = output_dir / "08_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    copy_if_exists(output_dir / "logs" / "quality_report.md", review_dir / "quality_report.md")
    copy_if_exists(output_dir / "logs" / "cleanup_warnings.md", review_dir / "cleanup_warnings.md")
    copy_if_exists(output_dir / "00_manifest" / "chapter_boundaries.json", review_dir / "chapter_boundaries.json")
    write_low_confidence(output_dir, review_dir, args.confidence_threshold)
    write_chapter_summary(output_dir, review_dir)
    write_glossary_review(output_dir, review_dir)
    write_docx_index(output_dir, review_dir)
    write_readme(output_dir, review_dir)
    print(review_dir)


if __name__ == "__main__":
    main()
