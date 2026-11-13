@echo off
chcp 65001 >nul
rem Frontend build: output goes to backend/app/static
setlocal
cd /d "%~dp0..\frontend"

if not exist "node_modules" (
    echo Installing frontend dependencies ...
    npm install
    if errorlevel 1 (
        echo npm install failed.
        pause
        exit /b 1
    )
)

echo Building frontend ...
npm run build
if errorlevel 1 (
    echo Frontend build failed.
    pause
    exit /b 1
)

echo Done: build output written to backend\app\static
endlocal
