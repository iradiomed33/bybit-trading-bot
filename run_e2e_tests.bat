@echo off
REM Quick start script for E2E tests (Windows)

echo ========================================
echo   E2E Tests Quick Start
echo ========================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Node.js is not installed. Please install Node.js 18+ first.
    exit /b 1
)

echo OK: Node.js found
node --version

REM Check if we're in the right directory
if not exist "tests\e2e\package.json" (
    echo Error: Please run this script from the project root directory
    exit /b 1
)

cd tests\e2e

REM Install dependencies if needed
if not exist "node_modules" (
    echo.
    echo Installing dependencies...
    call npm install
) else (
    echo OK: Dependencies already installed
)

REM Install Playwright browsers if needed
if not exist "node_modules\@playwright\test" (
    echo.
    echo Installing Playwright browsers...
    call npx playwright install --with-deps chromium
) else (
    echo OK: Playwright browsers already installed
)

echo.
echo ========================================
echo   Ready to run tests!
echo ========================================
echo.
echo Available commands:
echo   npm test              - Run all tests (headless)
echo   npm run test:ui       - Interactive UI mode
echo   npm run test:headed   - With visible browser
echo   npm run test:debug    - Debug mode
echo.
echo Starting tests in 3 seconds...
timeout /t 3 /nobreak >nul

call npm test
