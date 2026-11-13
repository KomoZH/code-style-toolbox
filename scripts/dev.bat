@echo off
chcp 65001 >nul
rem Dev mode: uvicorn --reload + vite dev (two processes)
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -q -r backend\requirements.txt
)

echo Starting backend (uvicorn --reload, :18765) ...
start "cst-backend" cmd /k "cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18765"

echo Starting frontend (vite dev, :5173) ...
start "cst-frontend" cmd /k "cd frontend && npm run dev"

echo Dev mode started: frontend http://127.0.0.1:5173/ (/api proxied to 18765)
endlocal
