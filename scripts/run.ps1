# One-click start (source mode, PowerShell): create venv, install deps, start backend
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[1/3] Creating virtual environment .venv ..."
    python -m venv .venv
}

Write-Host "[2/3] Installing backend dependencies ..."
& $venvPython -m pip install -q -r backend\requirements.txt

if (-not (Test-Path "backend\app\static\index.html")) {
    Write-Host "Note: frontend build not found at backend\app\static\index.html"
    Write-Host "Run scripts\build_frontend.bat first, otherwise only the API is available."
}

Write-Host "[3/3] Starting server ..."
Set-Location backend
& $venvPython -m app.main
