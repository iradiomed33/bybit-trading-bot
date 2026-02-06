#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Debug import issues - more aggressive."""

import sys

import traceback


# Show Python info

print(f"Python: {sys.executable}", flush=True)


print("\nTrying to import execution module...", flush=True)


try:

    # First just try the package

    print("Step 1: Import execution package", flush=True)

    print("✓ execution package imported", flush=True)

except Exception as e:

    print("✗ Failed to import execution package", flush=True)

    traceback.print_exc()

    sys.exit(1)


try:

    # Try trade_metrics directly

    print("Step 2: Import execution.trade_metrics", flush=True)

    sys.stdout.flush()

    sys.stderr.flush()

    print("✓ execution.trade_metrics imported", flush=True)

except Exception as e:

    print("✗ Failed to import trade_metrics", flush=True)

    traceback.print_exc()

    sys.exit(1)


print("✓ All imports successful", flush=True)
