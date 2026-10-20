$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir   = Join-Path $scriptDir ".venv"
$isAdmin   = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Refresh-Path

Write-Host "`n=== Audiobook Toolkit - Installer ===`n" -ForegroundColor Cyan

$needPython = -not (Get-Command python -ErrorAction SilentlyContinue)
$needFFmpeg = -not (Get-Command ffmpeg -ErrorAction SilentlyContinue)

if (($needPython -or $needFFmpeg) -and -not $isAdmin) {
    Write-Host "Requesting admin rights for Python/FFmpeg install..." -ForegroundColor Yellow
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
    } catch {
        Write-Host "Elevation cancelled. Re-run install.ps1." -ForegroundColor Red
        Read-Host "Press Enter"; exit 1
    }
    Refresh-Path
}

if ($needPython) {
    Write-Host "Installing Python 3.12..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    Refresh-Path
}
if ($needFFmpeg) {
    Write-Host "Installing FFmpeg..." -ForegroundColor Yellow
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    Refresh-Path
}

if (Test-Path $venvDir) {
    Write-Host "venv already exists." -ForegroundColor Green
} else {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $venvDir
}

$pip    = Join-Path $venvDir "Scripts\pip.exe"
$pyVenv = Join-Path $venvDir "Scripts\python.exe"

& $pip install --upgrade pip
Write-Host "Installing AI packages (this may take a while)..." -ForegroundColor Cyan
& $pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
& $pip install stable-ts rapidfuzz pydub scipy streamlit pocket-tts deepfilternet-rs

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "  ALL DONE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Read-Host "Press Enter to close"
