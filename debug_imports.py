#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Debug import issues."""

import sys

import traceback

import os


# Show Python info

print(f"Python executable: {sys.executable}")

print(f"Python version: {sys.version}")

print(f"Working directory: {os.getcwd()}")

print(f"sys.path: {sys.path[:3]}")

print()


files_to_test = [

    "execution.trade_metrics",

    "execution.backtest_reporter",

    "execution.paper_trading_simulator",

    "execution.backtest_runner",

    "tests.test_backtest_runner",

]


for module_name in files_to_test:

    print(f"\n{'=' * 60}")

    print(f"Testing: {module_name}")

    print(f"{'=' * 60}")

    sys.stdout.flush()

    sys.stderr.flush()

    try:

        print(f"Importing {module_name}...")

        sys.stdout.flush()

        mod = __import__(module_name, fromlist=[""])

        print(f"✓ {module_name} imported successfully")

        print(f"  Module file: {getattr(mod, '__file__', 'N/A')}")

    except SystemExit as e:

        print(f"✗ {module_name} called sys.exit({e.code})")

    except Exception as e:

        print(f"✗ {module_name} FAILED to import")

        print(f"Error type: {type(e).__name__}")

        print(f"Error message: {str(e)}")

        print("\nFull traceback:")

        traceback.print_exc()

    sys.stdout.flush()

    sys.stderr.flush()
