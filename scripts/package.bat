@echo off
chcp 65001 >nul
rem Full packaging: frontend build + PyInstaller --onedir -> dist/CodeStyleToolbox/
setlocal
cd /d "%~dp0.."

echo [1/4] Building frontend ...
call scripts\build_frontend.bat
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating virtual environment .venv ...
    python -m venv .venv
)

echo [3/4] Installing backend dependencies (incl. PyInstaller) ...
".venv\Scripts\python.exe" -m pip install -q -r backend\requirements.txt
if errorlevel 1 exit /b 1

echo [4/4] Packaging with PyInstaller ...
cd backend
"..\.venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm toolbox.spec
if errorlevel 1 (
    cd ..
    echo PyInstaller packaging failed.
    exit /b 1
)
cd ..

rem Copy examples and presets next to the exe (portable package)
if exist "backend\dist\CodeStyleToolbox" (
    xcopy /E /I /Y examples "backend\dist\CodeStyleToolbox\examples" >nul
    xcopy /E /I /Y data\presets "backend\dist\CodeStyleToolbox\data\presets" >nul
    echo.
    echo Packaging complete: backend\dist\CodeStyleToolbox\CodeStyleToolbox.exe
    echo Double-click to run (portable; data directory is next to the exe)
) else (
    echo Packaging failed. Check the PyInstaller output above.
    exit /b 1
)
endlocal
