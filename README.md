# JP LN OCR EPUB Skill

Codex/OpenClaw skill for Japanese vertical light-novel OCR, review-first Chinese translation, DOCX review files, and later EPUB packaging.

## Quick Setup on Windows

GPU CUDA 13.0:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode gpu-cu130
```

CPU fallback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode cpu
```

The installer creates `.venv`, installs Paddle/PaddleOCR and helper libraries, and checks the environment.

## Configure

Copy and edit:

```powershell
Copy-Item assets\config.example.yaml config.yaml
```

Set:

```yaml
input:
  path: "C:/path/to/book/images"

output:
  dir: "C:/path/to/output"
```

For translation, set:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
```

## Run Stages

Scan image folder:

```powershell
.\.venv\Scripts\python.exe scripts\book_pipeline.py scan --config config.yaml
```

OCR a page range:

```powershell
.\.venv\Scripts\python.exe scripts\ocr_paddle_book.py --config config.yaml --start-page 12 --end-page 60
```

Clean OCR and extract glossary candidates:

```powershell
.\.venv\Scripts\python.exe scripts\clean_ocr_japanese.py `
  --input-dir output\03_ordered_jp `
  --output-dir output\04_cleaned_jp `
  --glossary-csv output\05_glossary\glossary_candidates.csv `
  --warnings-md output\logs\cleanup_warnings.md
```

Detect chapter boundaries:

```powershell
.\.venv\Scripts\python.exe scripts\detect_chapters.py `
  --input-dir output\04_cleaned_jp `
  --output output\00_manifest\chapter_boundaries.json
```

Export DOCX review files:

```powershell
.\.venv\Scripts\python.exe scripts\export_docx_chapter.py `
  --title "第一章 白与黑的景色中" `
  --jp output\04_cleaned_jp\chapter_01.jp.md `
  --zh output\06_translated_zh\chapter_01.zh.md `
  --output-dir output\chapters `
  --prefix ch001
```

## Review-First Workflow

Do not build EPUB before review:

1. OCR review in Word.
2. Translation review in Word.
3. EPUB packaging after both are stable.

