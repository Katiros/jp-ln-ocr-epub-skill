---
name: jp-ln-ocr-epub
description: Process a folder of Japanese vertical light-novel page images into OCR text, Chinese translation, chapter DOCX files, and an EPUB using a release-template EPUB. Use when the user provides a whole book image folder, asks for Japanese vertical novel OCR, ruby/furigana handling, DeepSeek translation, chapter-based Word files, or EPUB production.
---

# JP LN OCR EPUB

Use this skill for review-first full-book Japanese light-novel image workflows:

```text
image folder -> manifest -> PaddleOCR -> vertical text reconstruction
-> OCR review package -> reviewed Japanese manuscript
-> DeepSeek translation -> translation review package
-> EPUB built from a template EPUB
```

## Inputs

Ask for or infer these paths:

- `input_dir`: folder containing the full book image set.
- `output_dir`: folder for generated manifest, OCR, DOCX, translation, and EPUB files.
- `template_epub`: optional EPUB whose CSS, fonts, and structure should be reused.
- `config`: optional YAML config. If absent, create one from `assets/config.example.yaml`.

Images may include cover, color pages, illustrations, title pages, table of contents, copyright pages, blank pages, and vertical body text.

## Required Tools

Prefer local deterministic tools for OCR and packaging:

- OCR: PaddleOCR / PaddlePaddle, with Japanese recognition.
- DOCX: `python-docx`.
- EPUB: Python `zipfile`, `beautifulsoup4`/`lxml`, or an EPUB library if already installed.
- Translation: DeepSeek API using `DEEPSEEK_API_KEY`.

Do not use DeepSeek for OCR unless the user explicitly has a vision/OCR-capable DeepSeek endpoint. Use DeepSeek for translation after OCR.

## Windows Setup

Prefer the bundled setup script instead of manual `pip` commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode gpu-cu130
```

Use CPU mode when GPU/CUDA is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode cpu
```

The script creates `.venv`, installs Paddle/PaddleOCR and DOCX dependencies, uses a China mainland PyPI mirror by default, and runs an environment check.

The Windows setup is skill-local by default:

```text
.venv/             shared Python environment for Codex/OpenClaw
.cache/wheels/     Paddle wheel cache
.cache/paddle*/    Paddle/PaddleOCR cache
.cache/paddlex/    PaddleX model cache
.cache/pip/        pip cache
```

When Codex and OpenClaw run on the same machine, both should call `.venv\Scripts\python.exe` from this skill directory instead of creating separate environments.

## Review Gates

Do not rush from OCR to translation or from translation to EPUB. Use explicit review gates:

1. **OCR review gate**
   - Produce raw OCR JSON, ordered Japanese text, and `quality_report.md`.
   - Stop for user review unless the user explicitly asks to continue.
   - Let the user correct OCR, page types, chapter splits, ruby handling, and glossary entries.

2. **Translation review gate**
   - Translate only reviewed Japanese chapter text.
   - Produce chapter Markdown/DOCX and translation notes.
   - Stop for user review before EPUB production.

3. **EPUB gate**
   - Build EPUB only after reviewed translation is available.
   - Treat EPUB as a packaging step, not as the place to fix OCR or translation errors.

## Workflow

1. **Scan the book folder**
   - Natural-sort image filenames.
   - Create `00_manifest/manifest.json`.
   - Classify pages as `cover`, `illustration`, `body`, `toc`, `copyright`, `blank`, or `unknown`.
   - Do not discard skipped pages; record them in the manifest.
   - Command:
     ```bash
     python scripts/book_pipeline.py scan --config config.yaml
     ```

2. **OCR body pages**
   - Use PaddleOCR as the default engine.
   - Keep raw OCR JSON per page in `output/02_ocr_raw/`.
   - Detect vertical text regions and order them by Japanese reading order:
     top-to-bottom inside each column, columns right-to-left.
   - Store ordered text per page in `output/03_ordered_jp/`.
   - Generate `logs/quality_report.md`.
   - Command:
     ```bash
     python scripts/ocr_paddle_book.py --config config.yaml
     ```

3. **Handle ruby/furigana**
   - Ordinary pronunciation ruby may be removed from body text.
   - Ruby that changes meaning, names a character, or gives an alternate reading must be preserved in `glossary.yaml`.
   - Examples:
     - `上条当麻 / かみじょうとうま` -> glossary entry.
     - `魔神 / ネフテュス` -> preserve because ruby changes identity/meaning.
   - Never silently merge ruby into the main text as `上かみ条じょう...`.
   - If automatic ruby separation is uncertain, preserve the original line in `uncertain_items.md` and keep the body text conservative.

4. **Detect section markers and scene breaks**
   - Do not delete every isolated number as a page number.
   - Treat an isolated number near page corners as a likely page number.
   - Treat an isolated number inside the text flow, surrounded by whitespace or followed by new prose, as a section marker.
   - Preserve section markers as Markdown headings during review:
     ```markdown
     ## 2
     ```

5. **Build glossary candidates**
   - Extract likely person names, katakana names, terms joined by `=`, `＝`, `・`, and special ruby pairs.
   - Write candidates to `05_glossary/glossary_candidates.csv`.
   - If a relevant wiki is configured, use `scripts/import_wiki_glossary.py` to prefill `05_glossary/wiki_glossary_candidates.csv`.
   - If the wiki API blocks automated access, import a manually exported CSV with `--manual-csv`.
   - Treat wiki results as review candidates, not final truth; the user confirms `zh` and `status`.
   - Do not force final Chinese renderings automatically; mark them `pending_review`.

6. **Rebuild paragraphs**
   - Remove page numbers, page headers, footers, and isolated center digits.
   - Preserve dialogue blocks and nested quote distinctions.
   - Merge across page breaks when the previous page ends mid-sentence or with an unclosed quote.
   - Keep chapter boundaries. If uncertain, use image filename ranges until the user confirms titles.

7. **Stop for OCR review**
   - Ask the user to inspect `03_ordered_jp`, page types in manifest, and `quality_report.md`.
   - Do not translate unreviewed OCR unless the user explicitly chooses a fast draft mode.

8. **Generate chapter DOCX files**
   - Create one DOCX per chapter for OCR source text.
   - Preserve original paragraph structure.
   - Use stable styles:
     - `Chapter Title`
     - `JP Original`
     - `CN Translation`
     - `OCR Warning`
     - `Illustration Ref`

9. **Translate with DeepSeek**
   - Translate by chapter chunks, not isolated pages.
   - Include glossary, previous context, and chapter summary where useful.
   - Output translation plus new glossary candidates and OCR uncertainty notes.
   - Keep literary Chinese natural, not word-for-word.

10. **Stop for translation review**
   - Ask the user to inspect translated chapters and terminology.
   - Do not build EPUB before translation review unless explicitly requested.

11. **Build EPUB**
   - If a template EPUB is provided, unpack it and preserve CSS, fonts, metadata structure, and cover conventions.
   - Replace or generate XHTML chapter files.
   - Generate/refresh TOC and spine.
   - Repack using EPUB zip rules: `mimetype` must be first and uncompressed.

12. **Validate**
   - Confirm all body pages have OCR output or explicit skip reasons.
   - Confirm chapter files exist.
   - Confirm glossary is updated.
   - Confirm EPUB opens structurally: mimetype, container, OPF, spine, nav/NCX as applicable.

13. **Clean temporary files**
   - After a completed run, remove disposable temp folders and Python script caches.
   - Keep review artifacts, OCR JSON, ordered Japanese text, cleaned Japanese text, glossary CSV, DOCX, and logs.
   - Do not delete `.cache/wheels`, downloaded OCR models, or `.venv` by default; they are reusable runtime assets.
   - Command:
     ```powershell
     powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Step cleanup -OutputDir <output_dir>
     ```
   - Only use `-IncludeVenvPycache` for a deep cleanup when startup speed is less important than disk cleanup.

## Output Layout

Use this layout unless the user asks otherwise:

```text
output/
  00_manifest/
    manifest.json
  01_preprocessed/
  02_ocr_raw/
    page_0001.json
  03_ordered_jp/
    page_0001.txt
  04_cleaned_jp/
    chapter_01.txt
  05_glossary/
    glossary.yaml
  06_translated_zh/
    chapter_01.zh.md
  07_bilingual/
    chapter_01.bilingual.md
  08_review/
    README_REVIEW.md
    low_confidence_pages.md
    cleanup_warnings.md
    glossary_candidates.csv
    chapter_boundaries_review.md
    docx_review_index.md
  logs/
    quality_report.md
    errors.json
  glossary.yaml
  uncertain_items.md
  chapters/
    ch001_ocr.docx
    ch001_bilingual.docx
    ch001_zh.docx
  markdown/
    ch001_bilingual.md
    ch001_zh.md
  epub_work/
  final.epub
```

## User-Facing Language

Use Simplified Chinese for user-facing review artifacts by default:

- `README_OUTPUTS.md`
- `quality_report.md`
- `cleanup_warnings.md`
- DOCX headings and review notes
- translation notes and glossary review instructions

Keep technical directory names and machine-readable keys in English for tool compatibility:

- `00_manifest`
- `02_ocr_raw`
- `03_ordered_jp`
- `chapter_boundaries.json`
- JSON/YAML/CSV field names

If the user requests another language, follow that request for user-facing files only.

## Batch/Resume Rules

Full books are long-running. Always support resume behavior:

- Reuse existing `02_ocr_raw` and `03_ordered_jp` unless the user asks to rerun OCR.
- Reuse existing translations unless the source chunk or glossary changed.
- Save state after each page and each chapter.
- If a step fails, report the exact page/chapter and continue only when safe.

## Current Executable Stages

This skill currently provides executable scripts for:

- `scripts/book_pipeline.py scan`: image discovery, natural sorting, numbered output directory setup, and manifest creation.
- `scripts/ocr_paddle_book.py`: PaddleOCR batch OCR, raw JSON output, simple vertical right-to-left ordering, OCR-derived page classification, and quality report generation.
- `scripts/clean_ocr_japanese.py`: first-pass Japanese cleanup, section marker preservation, ruby-contamination warnings, and glossary candidate extraction.
- `scripts/import_wiki_glossary.py`: import glossary candidates from a MediaWiki-compatible wiki such as Toaru HuijiWiki.
- `scripts/deepseek_translate.py`: single reviewed text file translation with DeepSeek.
- `scripts/export_docx_chapter.py`: export reviewed Japanese Markdown and optional Chinese Markdown to `*_ocr.docx`, `*_zh.docx`, and `*_bilingual.docx`.
- `scripts/build_review_pack.py`: collect human-review materials into `08_review/`.

Treat DOCX chapter export, chapter merge, and EPUB packaging as later stages unless the user asks to implement them.

## DeepSeek Prompt Contract

Use a structured prompt:

```text
You are translating a Japanese vertical light novel into Simplified Chinese.
Preserve chapter structure, paragraph breaks, dialogue rhythm, names, honorific nuance, and glossary consistency.
If the Japanese source appears corrupted by OCR, mark it as [OCR疑问: ...] and infer only when context is strong.
Return:
1. Chinese translation
2. New or changed glossary entries
3. OCR uncertainty notes
```

## OpenClaw Usage

If running in OpenClaw or another AgentSkills-compatible agent:

1. Copy this folder to the agent skills directory, for example:
   `~/.openclaw/skills/jp-ln-ocr-epub/`
2. Make the skill visible to the target agent in that agent's skills config.
3. Give a task with explicit paths:

```text
Use jp-ln-ocr-epub.
input_dir: G:/books/example/images
output_dir: G:/books/example/output
template_epub: G:/books/templates/release_template.epub

Run the full pipeline:
scan images, OCR body pages with PaddleOCR, generate chapter OCR DOCX files,
translate with DeepSeek, generate bilingual chapter DOCX files, build EPUB from template,
and produce glossary.yaml plus uncertain_items.md.
```

## Reference Files

Load these only when needed:

- `references/ocr_rules.md`: vertical OCR, ruby, page classification, and paragraph repair rules.
- `references/translation_style.md`: Chinese light-novel translation style and DeepSeek prompt details.
- `references/epub_rules.md`: template EPUB reuse and packaging checks.
