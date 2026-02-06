#!/usr/bin/env python

# -*- coding: utf-8 -*-

import sys


sys.path.insert(0, ".")


try:

    from tests import test_backtest_runner

    print(f"✓ Imported test_backtest_runner: {len(dir(test_backtest_runner))} items")

    print("Classes found:")

    for item in dir(test_backtest_runner):

        if item.startswith("Test"):

            print(f"  - {item}")

except Exception as e:

    print(f"✗ Failed to import: {e}")

    import traceback

    traceback.print_exc()
