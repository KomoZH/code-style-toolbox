@echo off
chcp 65001 >nul
rem One-click start (source mode): create venv, install deps, start backend
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Python not found on PATH. Please install Python 3.13 and add it to PATH.
        pause
        exit /b 1
    )
)

echo [2/3] Installing backend dependencies ...
".venv\Scripts\python.exe" -m pip install -q -r backend\requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

if not exist "backend\app\static\index.html" (
    echo Note: frontend build not found at backend\app\static\index.html
    echo Run scripts\build_frontend.bat first, otherwise only the API is available.
)

echo [3/3] Starting server ...
cd backend
"..\.venv\Scripts\python.exe" -m app.main
endlocal
