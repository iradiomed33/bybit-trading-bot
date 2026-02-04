#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launch API server with frontend dashboard.

Usage:
    python run_api.py
    
Access: http://localhost:8000
API docs: http://localhost:8000/docs
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from api.app import app

def main():
    print("""
    ===================================================
    Bybit Trading Bot - API Dashboard Server
    ===================================================
    
    Starting API Server...
    
    Dashboard:  http://localhost:8000
    API Docs:   http://localhost:8000/docs
    WebSocket:  ws://localhost:8000/ws
    
    Press Ctrl+C to stop the server.
    """)
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
