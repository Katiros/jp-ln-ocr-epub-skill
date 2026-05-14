param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("scan", "ocr", "clean", "detect-chapters", "export-docx")]
    [string]$Step,

    [string]$Config = "assets\config.example.yaml",
    [string]$OutputDir = "",
    [int]$StartPage = 0,
    [int]$EndPage = 0
)

$ErrorActionPreference = "Stop"
$SkillRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SkillRoot

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
    "export-docx" {
        throw "Use scripts\export_docx_chapter.py directly for now because it needs chapter file paths."
    }
}

