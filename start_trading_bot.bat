@echo off
REM Bybit Trading Bot - Paper Mode Launcher
REM Автоматически запускает бота в paper mode

chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ===================================================
echo Bybit Trading Bot - Paper Mode
echo ===================================================
echo.
echo Запускаем бота для генерации сигналов...
echo (Нажмите Ctrl+C для остановки)
echo.

cd /d "%~dp0"
echo NO | venv\Scripts\python.exe cli.py paper

pause
