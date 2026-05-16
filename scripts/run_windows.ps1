param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("doctor", "scan", "ocr", "clean", "detect-chapters", "merge-chapters", "import-wiki-glossary", "draft-glossary", "build-translation-glossary", "write-readme", "review-pack", "export-docx", "cleanup", "first-chapter-review")]
    [string]$Step,

    [string]$Config = "assets\config.example.yaml",
    [string]$OutputDir = "",
    [int]$StartPage = 0,
    [int]$EndPage = 0,
    [int]$Chapter = 1,
    [switch]$IncludeVenvPycache,
    [string]$ManualWikiCsv = "",
    [string]$ManualWikiText = "",
    [string]$SeedGlossary = "",
    [switch]$UseDeepSeekGlossaryDraft
)

$ErrorActionPreference = "Stop"
$SkillRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SkillRoot
$CacheRoot = Join-Path $SkillRoot ".cache"
$env:PADDLE_HOME = Join-Path $CacheRoot "paddle"
$env:PADDLEOCR_HOME = Join-Path $CacheRoot "paddleocr"
$env:PADDLE_PDX_CACHE_HOME = Join-Path $CacheRoot "paddlex"
$env:PADDLEX_HOME = Join-Path $CacheRoot "paddlex"
$env:HF_HOME = Join-Path $CacheRoot "huggingface"
$env:MODELSCOPE_CACHE = Join-Path $CacheRoot "modelscope"
$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
New-Item -ItemType Directory -Force -Path $CacheRoot,$env:PADDLE_HOME,$env:PADDLEOCR_HOME,$env:PADDLE_PDX_CACHE_HOME,$env:HF_HOME,$env:MODELSCOPE_CACHE,$env:PIP_CACHE_DIR | Out-Null

$PythonExe = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Venv not found. Run scripts\install_windows.ps1 first."
}

switch ($Step) {
    "doctor" {
        & $PythonExe "scripts\doctor.py"
    }
    "scan" {
        & $PythonExe "scripts\book_pipeline.py" scan --config $Config
    }
    "ocr" {
        $args = @("scripts\ocr_paddle_book.py", "--config", $Config)
        if ($OutputDir) { $args += @("--output-dir", $OutputDir) }
        if ($StartPage -gt 0) { $args += @("--start-page", "$StartPage") }
        if ($EndPage -gt 0) { $args += @("--end-page", "$EndPage") }
        & $PythonExe @args
    }
    "clean" {
        if (-not $OutputDir) { throw "OutputDir is required for clean." }
        & $PythonExe "scripts\clean_ocr_japanese.py" `
            --input-dir (Join-Path $OutputDir "03_ordered_jp") `
            --output-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --glossary-csv (Join-Path $OutputDir "05_glossary\glossary_candidates.csv") `
            --warnings-md (Join-Path $OutputDir "logs\cleanup_warnings.md")
    }
    "detect-chapters" {
        if (-not $OutputDir) { throw "OutputDir is required for detect-chapters." }
        & $PythonExe "scripts\detect_chapters.py" `
            --input-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --output (Join-Path $OutputDir "00_manifest\chapter_boundaries.json")
    }
    "merge-chapters" {
        if (-not $OutputDir) { throw "OutputDir is required for merge-chapters." }
        & $PythonExe "scripts\merge_chapter_pages.py" `
            --input-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --boundaries (Join-Path $OutputDir "00_manifest\chapter_boundaries.json") `
            --output-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --chapter $Chapter
    }
    "import-wiki-glossary" {
        if (-not $OutputDir) { throw "OutputDir is required for import-wiki-glossary." }
        $args = @(
            "scripts\import_wiki_glossary.py",
            "--terms-csv", (Join-Path $OutputDir "05_glossary\glossary_candidates.csv"),
            "--output", (Join-Path $OutputDir "05_glossary\wiki_glossary_candidates.csv")
        )
        if ($ManualWikiCsv) { $args += @("--manual-csv", $ManualWikiCsv) }
        if ($ManualWikiText) { $args += @("--manual-text", $ManualWikiText) }
        if ($ManualWikiCsv -or $ManualWikiText) { $args += @("--offline") }
        & $PythonExe @args
    }
    "draft-glossary" {
        if (-not $OutputDir) { throw "OutputDir is required for draft-glossary." }
        $args = @(
            "scripts\draft_glossary.py",
            "--candidates-csv", (Join-Path $OutputDir "05_glossary\glossary_candidates.csv"),
            "--output", (Join-Path $OutputDir "05_glossary\glossary_draft.csv")
        )
        $wiki = Join-Path $OutputDir "05_glossary\wiki_glossary_candidates.csv"
        if (Test-Path $wiki) { $args += @("--wiki-csv", $wiki) }
        if ($SeedGlossary) { $args += @("--seed-csv", $SeedGlossary) }
        if ($UseDeepSeekGlossaryDraft) { $args += @("--deepseek") }
        & $PythonExe @args
    }
    "build-translation-glossary" {
        if (-not $OutputDir) { throw "OutputDir is required for build-translation-glossary." }
        & $PythonExe "scripts\build_translation_glossary.py" `
            --input (Join-Path $OutputDir "05_glossary\glossary_draft.csv") `
            --output (Join-Path $OutputDir "05_glossary\glossary_for_translation.txt") `
            --rejected-csv (Join-Path $OutputDir "05_glossary\glossary_for_translation_rejected.csv")
    }
    "write-readme" {
        if (-not $OutputDir) { throw "OutputDir is required for write-readme." }
        & $PythonExe "scripts\write_output_readme.py" --output-dir $OutputDir
    }
    "review-pack" {
        if (-not $OutputDir) { throw "OutputDir is required for review-pack." }
        & $PythonExe "scripts\build_review_pack.py" --output-dir $OutputDir
    }
    "export-docx" {
        if (-not $OutputDir) { throw "OutputDir is required for export-docx." }
        $prefix = "ch{0:D3}" -f $Chapter
        $jp = Join-Path $OutputDir ("04_cleaned_jp\chapter_{0:D2}.jp.md" -f $Chapter)
        $zh = Join-Path $OutputDir ("06_translated_zh\chapter_{0:D2}.zh.md" -f $Chapter)
        $args = @(
            "scripts\export_docx_chapter.py",
            "--title", ("Chapter {0}" -f $Chapter),
            "--jp", $jp,
            "--output-dir", (Join-Path $OutputDir "chapters"),
            "--prefix", $prefix
        )
        if (Test-Path $zh) { $args += @("--zh", $zh) }
        & $PythonExe @args
    }
    "cleanup" {
        $args = @("scripts\cleanup_runtime.py", "--runtime")
        if ($OutputDir) { $args += @("--output-dir", $OutputDir) }
        if ($IncludeVenvPycache) { $args += @("--include-venv-pycache") }
        & $PythonExe @args
    }
    "first-chapter-review" {
        if (-not $OutputDir) { throw "OutputDir is required for first-chapter-review." }
        & $PythonExe "scripts\book_pipeline.py" scan --config $Config
        $ocrArgs = @("scripts\ocr_paddle_book.py", "--config", $Config, "--output-dir", $OutputDir)
        if ($StartPage -gt 0) { $ocrArgs += @("--start-page", "$StartPage") }
        if ($EndPage -gt 0) { $ocrArgs += @("--end-page", "$EndPage") }
        & $PythonExe @ocrArgs
        & $PythonExe "scripts\clean_ocr_japanese.py" `
            --input-dir (Join-Path $OutputDir "03_ordered_jp") `
            --output-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --glossary-csv (Join-Path $OutputDir "05_glossary\glossary_candidates.csv") `
            --warnings-md (Join-Path $OutputDir "logs\cleanup_warnings.md")
        & $PythonExe "scripts\detect_chapters.py" `
            --input-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --output (Join-Path $OutputDir "00_manifest\chapter_boundaries.json")
        $draftArgs = @(
            "scripts\draft_glossary.py",
            "--candidates-csv", (Join-Path $OutputDir "05_glossary\glossary_candidates.csv"),
            "--output", (Join-Path $OutputDir "05_glossary\glossary_draft.csv")
        )
        $wiki = Join-Path $OutputDir "05_glossary\wiki_glossary_candidates.csv"
        if (Test-Path $wiki) { $draftArgs += @("--wiki-csv", $wiki) }
        & $PythonExe @draftArgs
        & $PythonExe "scripts\build_translation_glossary.py" `
            --input (Join-Path $OutputDir "05_glossary\glossary_draft.csv") `
            --output (Join-Path $OutputDir "05_glossary\glossary_for_translation.txt") `
            --rejected-csv (Join-Path $OutputDir "05_glossary\glossary_for_translation_rejected.csv")
        & $PythonExe "scripts\merge_chapter_pages.py" `
            --input-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --boundaries (Join-Path $OutputDir "00_manifest\chapter_boundaries.json") `
            --output-dir (Join-Path $OutputDir "04_cleaned_jp") `
            --chapter $Chapter
        $prefix = "ch{0:D3}" -f $Chapter
        & $PythonExe "scripts\export_docx_chapter.py" `
            --title ("Chapter {0}" -f $Chapter) `
            --jp (Join-Path $OutputDir ("04_cleaned_jp\chapter_{0:D2}.jp.md" -f $Chapter)) `
            --output-dir (Join-Path $OutputDir "chapters") `
            --prefix $prefix
        & $PythonExe "scripts\write_output_readme.py" --output-dir $OutputDir
        & $PythonExe "scripts\build_review_pack.py" --output-dir $OutputDir
        & $PythonExe "scripts\cleanup_runtime.py" --output-dir $OutputDir --runtime
    }
}
