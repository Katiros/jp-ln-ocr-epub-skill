param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("scan", "ocr", "clean", "detect-chapters", "import-wiki-glossary", "write-readme", "review-pack", "export-docx")]
    [string]$Step,

    [string]$Config = "assets\config.example.yaml",
    [string]$OutputDir = "",
    [int]$StartPage = 0,
    [int]$EndPage = 0
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
    "import-wiki-glossary" {
        if (-not $OutputDir) { throw "OutputDir is required for import-wiki-glossary." }
        & $PythonExe "scripts\import_wiki_glossary.py" `
            --terms-csv (Join-Path $OutputDir "05_glossary\glossary_candidates.csv") `
            --output (Join-Path $OutputDir "05_glossary\wiki_glossary_candidates.csv")
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
        throw "Use scripts\export_docx_chapter.py directly for now because it needs chapter file paths."
    }
}
