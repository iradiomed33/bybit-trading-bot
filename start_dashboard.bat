@echo off
REM Quick start script for the dashboard (Windows)

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║         Bybit Trading Bot - Dashboard Launcher                ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo 📋 Starting dashboard...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found!
    pause
    exit /b 1
)

echo ✅ Python found: 
python --version

REM Check if venv exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install requirements
echo 📥 Installing dependencies...
pip install -r requirements.txt >nul 2>&1

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed
echo.
echo 🚀 Starting API server...
echo.
echo Dashboard will be available at: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python run_api.py

pause
