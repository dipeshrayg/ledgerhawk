# One-command run: starts the API (seeding itself from checked-in fixtures)
# and the web dev server. Fresh clone -> `./run.ps1` -> dashboard at
# http://localhost:5173.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$root\.venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv "$root\.venv"
}
$py = "$root\.venv\Scripts\python.exe"

Write-Host "Installing API dependencies..."
& $py -m pip install -q -r "$root\api\requirements.txt"

Write-Host "Starting API on http://localhost:8000 ..."
$apiProc = Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
    -WorkingDirectory "$root\api" -PassThru -NoNewWindow

if (-not (Test-Path "$root\web\node_modules")) {
    Write-Host "Installing web dependencies..."
    Push-Location "$root\web"; npm install; Pop-Location
}

Write-Host "Starting web dev server on http://localhost:5173 ..."
$webProc = Start-Process -FilePath "npm" -ArgumentList "run", "dev", "--", "--port", "5173" `
    -WorkingDirectory "$root\web" -PassThru -NoNewWindow

Write-Host ""
Write-Host "LedgerHawk is running:"
Write-Host "  API   http://localhost:8000/api/health"
Write-Host "  Web   http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers."

try {
    Wait-Process -Id $apiProc.Id
} finally {
    Stop-Process -Id $apiProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $webProc.Id -Force -ErrorAction SilentlyContinue
}
