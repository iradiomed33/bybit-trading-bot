#!/bin/bash
# Quick start script for the dashboard

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         Bybit Trading Bot - Dashboard Launcher                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Steps:"
echo "  1. Install dependencies..."
echo "  2. Start API server..."
echo "  3. Open dashboard..."
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found!"
    exit 1
fi

echo "✅ Python found: $(python --version)"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate venv (Windows)
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Run API server
echo ""
echo "🚀 Starting API server..."
echo ""
echo "Dashboard will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
python run_api.py
