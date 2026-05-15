param(
    [ValidateSet("gpu-cu130", "cpu")]
    [string]$Mode = "gpu-cu130",

    [string]$VenvPath = ".venv",

    [string]$PypiIndex = "https://pypi.tuna.tsinghua.edu.cn/simple",

    [string]$PythonPath = "",

    [switch]$SkipPaddle
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    if ($PythonPath) {
        if (Test-Path $PythonPath) {
            return (Resolve-Path $PythonPath).Path
        }
        throw "PythonPath does not exist: $PythonPath"
    }
    $candidates = @("py", "python")
    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    throw "Python was not found. Install Python 3.10-3.12 and rerun this script."
}

function Invoke-Pip {
    param([string[]]$Arguments)
    & $script:PythonExe -m pip @Arguments
}

$SkillRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SkillRoot
$CacheRoot = Join-Path $SkillRoot ".cache"
$WheelDir = Join-Path $CacheRoot "wheels"
$PipCache = Join-Path $CacheRoot "pip"
$env:PADDLE_HOME = Join-Path $CacheRoot "paddle"
$env:PADDLEOCR_HOME = Join-Path $CacheRoot "paddleocr"
$env:PADDLE_PDX_CACHE_HOME = Join-Path $CacheRoot "paddlex"
$env:PADDLEX_HOME = Join-Path $CacheRoot "paddlex"
$env:HF_HOME = Join-Path $CacheRoot "huggingface"
$env:MODELSCOPE_CACHE = Join-Path $CacheRoot "modelscope"
$env:PIP_CACHE_DIR = $PipCache
New-Item -ItemType Directory -Force -Path $CacheRoot,$WheelDir,$PipCache,$env:PADDLE_HOME,$env:PADDLEOCR_HOME,$env:PADDLE_PDX_CACHE_HOME,$env:HF_HOME,$env:MODELSCOPE_CACHE | Out-Null

Write-Host "Skill root: $SkillRoot"
Write-Host "Skill-local cache: $CacheRoot"
$SystemPython = Resolve-Python
Write-Host "Using Python launcher: $SystemPython"

if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating venv: $VenvPath"
    & $SystemPython -m venv $VenvPath
}

$script:PythonExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $script:PythonExe)) {
    throw "Virtualenv Python not found: $script:PythonExe"
}

Write-Host "Upgrading pip tooling..."
Invoke-Pip @("install", "--upgrade", "pip", "setuptools", "wheel", "-i", $PypiIndex, "--trusted-host", ([uri]$PypiIndex).Host)

if (-not $SkipPaddle) {
    if ($Mode -eq "gpu-cu130") {
        $wheel = Join-Path $WheelDir "paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl"
        $wheelUrl = "https://paddle-whl.bj.bcebos.com/stable/cu130/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl"
        if (-not (Test-Path $wheel)) {
            Write-Host "Downloading PaddlePaddle GPU wheel for CUDA 13.0..."
            curl.exe -L --retry 20 --retry-delay 5 --connect-timeout 60 --continue-at - --output $wheel $wheelUrl
        } else {
            Write-Host "Using cached PaddlePaddle wheel: $wheel"
        }
        Invoke-Pip @("install", $wheel, "-i", $PypiIndex, "--trusted-host", ([uri]$PypiIndex).Host, "--timeout", "180", "--retries", "10")
    } else {
        Invoke-Pip @("install", "-r", "requirements-cpu.txt", "-i", $PypiIndex, "--trusted-host", ([uri]$PypiIndex).Host, "--timeout", "180", "--retries", "10")
    }
}

Write-Host "Installing OCR/export dependencies..."
Invoke-Pip @("install", "-r", "requirements.txt", "-i", $PypiIndex, "--trusted-host", ([uri]$PypiIndex).Host, "--timeout", "180", "--retries", "10")

Write-Host "Checking installation..."
& $script:PythonExe "scripts\paddleocr_notes.py"

Write-Host ""
Write-Host "Done."
Write-Host "Python: $script:PythonExe"
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\python.exe scripts\book_pipeline.py scan --config assets\config.example.yaml"
