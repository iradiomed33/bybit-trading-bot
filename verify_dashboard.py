#!/usr/bin/env python
"""
Verification checklist for Bybit Trading Bot Dashboard

Run this script to verify all components are in place:
    python verify_dashboard.py
"""

import os
import sys
import json
from pathlib import Path

class DashboardVerifier:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.successes = []
        self.root = Path(__file__).parent

    def check_file(self, filepath, description=""):
        """Check if a file exists"""
        full_path = self.root / filepath
        if full_path.exists():
            size = full_path.stat().st_size
            self.successes.append(f"✅ {filepath} ({size:,} bytes) {description}")
            return True
        else:
            self.errors.append(f"❌ {filepath} - MISSING")
            return False

    def check_directory(self, dirpath, description=""):
        """Check if a directory exists"""
        full_path = self.root / dirpath
        if full_path.is_dir():
            self.successes.append(f"✅ {dirpath}/ {description}")
            return True
        else:
            self.errors.append(f"❌ {dirpath}/ - MISSING")
            return False

    def check_module(self, module_name):
        """Check if a Python module can be imported"""
        try:
            __import__(module_name)
            self.successes.append(f"✅ Python module: {module_name}")
            return True
        except ImportError as e:
            self.warnings.append(f"⚠️  Python module '{module_name}' not installed: {e}")
            return False

    def verify_all(self):
        """Run all verification checks"""
        print("""
╔════════════════════════════════════════════════════════════════════════╗
║     Bybit Trading Bot - Dashboard Verification Checklist               ║
╚════════════════════════════════════════════════════════════════════════╝
        """)

        # Check backend files
        print("\n🔧 Backend Components:")
        self.check_file("api/app.py", "- FastAPI application")
        self.check_file("api/__init__.py", "- API package")
        self.check_file("config/settings.py", "- Configuration manager")
        self.check_file("config/bot_settings.json", "- Configuration file")
        self.check_file("utils/retry.py", "- Retry logic")

        # Check frontend files
        print("\n🎨 Frontend Components:")
        self.check_directory("static", "- Static files directory")
        self.check_file("static/index.html", "- Dashboard HTML")
        self.check_file("static/css/style.css", "- Dashboard styles")
        self.check_file("static/js/app.js", "- Dashboard JavaScript")

        # Check startup scripts
        print("\n🚀 Startup Scripts:")
        self.check_file("run_api.py", "- API server launcher")
        self.check_file("start_dashboard.bat", "- Windows launcher")
        self.check_file("start_dashboard.sh", "- Linux/Mac launcher")

        # Check documentation
        print("\n📚 Documentation:")
        self.check_file("DASHBOARD_SETUP.md", "- Setup guide")
        self.check_file("DASHBOARD_WELCOME.md", "- Welcome guide")
        self.check_file("API_DASHBOARD.md", "- API documentation")
        self.check_file("CONFIG_GUIDE.md", "- Configuration guide")

        # Check dependencies
        print("\n📦 Python Dependencies:")
        self.check_module("fastapi")
        self.check_module("uvicorn")
        self.check_module("websockets")
        self.check_module("requests")

        # Check directories
        print("\n📁 Required Directories:")
        self.check_directory("api", "- API package")
        self.check_directory("config", "- Configuration")
        self.check_directory("storage", "- Database storage")
        self.check_directory("logs", "- Log files")

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print verification summary"""
        print("\n" + "="*70)
        print("VERIFICATION REPORT")
        print("="*70)

        if self.successes:
            print(f"\n✅ SUCCESSES ({len(self.successes)}):")
            for success in self.successes[:10]:  # Show first 10
                print(f"   {success}")
            if len(self.successes) > 10:
                print(f"   ... and {len(self.successes) - 10} more ✅")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")

        # Overall status
        print("\n" + "="*70)
        if not self.errors:
            print("✅ ALL CHECKS PASSED - Dashboard is ready to run!")
            print("\n🚀 Next steps:")
            print("   1. Run: python run_api.py")
            print("   2. Open: http://localhost:8000")
            print("   3. Enjoy your dashboard!")
            return 0
        else:
            print(f"❌ {len(self.errors)} critical error(s) found!")
            print("   Please fix these issues before running the dashboard.")
            return 1

def main():
    verifier = DashboardVerifier()
    exit_code = verifier.verify_all()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
