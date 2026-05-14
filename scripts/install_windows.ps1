param(
    [ValidateSet("gpu-cu130", "cpu")]
    [string]$Mode = "gpu-cu130",

    [string]$VenvPath = ".venv",

    [string]$PypiIndex = "https://pypi.tuna.tsinghua.edu.cn/simple",

    [switch]$SkipPaddle
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
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

Write-Host "Skill root: $SkillRoot"
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
        $wheel = Join-Path $env:TEMP "paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl"
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

