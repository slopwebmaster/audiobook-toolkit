$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyVenv    = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pyVenv)) {
    Write-Host "Setup not complete. Run install.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter"; exit 1
}
$env:PATH = (Join-Path $scriptDir ".venv\Scripts") + ";" + $env:PATH
Write-Host "Starting Audiobook Toolkit... browser will open shortly." -ForegroundColor Cyan
& $pyVenv -m streamlit run (Join-Path $scriptDir "app.py") --server.headless=false --browser.gatherUsageStats=false
