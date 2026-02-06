#!/usr/bin/env python

# -*- coding: utf-8 -*-

import sys


print("Python version:", sys.version)


# Try importing standard lib


print("✓ decimal OK")


# Try numpy

try:

    import numpy

    print(f"✓ numpy {numpy.__version__} OK")

except ImportError as e:

    print(f"✗ numpy FAILED: {e}")


# Try pandas

try:

    import pandas

    print(f"✓ pandas {pandas.__version__} OK")

except ImportError as e:

    print(f"✗ pandas FAILED: {e}")


# Try execution modules

try:

    pass

    print("✓ trade_metrics OK")

except ImportError as e:

    print(f"✗ trade_metrics FAILED: {e}")


try:

    pass

    print("✓ paper_trading_simulator OK")

except ImportError as e:

    print(f"✗ paper_trading_simulator FAILED: {e}")


try:

    pass

    print("✓ backtest_runner OK")

except ImportError as e:

    print(f"✗ backtest_runner FAILED: {e}")
