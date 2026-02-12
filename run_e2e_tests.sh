#!/bin/bash

# Quick start script for E2E tests

set -e

echo "========================================"
echo "  E2E Tests Quick Start"
echo "========================================"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ Node.js found: $(node --version)"

# Check if we're in the right directory
if [ ! -f "tests/e2e/package.json" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

cd tests/e2e

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📦 Installing dependencies..."
    npm install
else
    echo "✅ Dependencies already installed"
fi

# Install Playwright browsers if needed
if [ ! -d "node_modules/@playwright/test" ]; then
    echo ""
    echo "🎭 Installing Playwright browsers..."
    npx playwright install --with-deps chromium
else
    echo "✅ Playwright browsers already installed"
fi

echo ""
echo "========================================"
echo "  Ready to run tests!"
echo "========================================"
echo ""
echo "Available commands:"
echo "  npm test              - Run all tests (headless)"
echo "  npm run test:ui       - Interactive UI mode"
echo "  npm run test:headed   - With visible browser"
echo "  npm run test:debug    - Debug mode"
echo ""
echo "Starting tests in 3 seconds..."
sleep 3

npm test
