#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Test NumPy import with error handling."""

import sys

import traceback


print("Attempting to import NumPy...", flush=True)

try:

    import numpy

    print(f"✓ NumPy imported: {numpy.__version__}", flush=True)

except Exception as e:

    print("✗ NumPy import failed", flush=True)

    print(f"Error type: {type(e).__name__}", flush=True)

    print(f"Error: {e}", flush=True)

    print("\nTraceback:", flush=True)

    traceback.print_exc()

    sys.exit(1)
