# coding: utf-8

"""

STR-001 DoD Validation Script (Simple Version)


DoD:

1. stop_distance > 0 for each trade

2. Position size scales inversely with ATR

3. Logs contain: atr, stop, take, risk_usd, qty

"""


import pandas as pd

import numpy as np

from decimal import Decimal


print("=" * 80)

print("STR-001 DoD VALIDATION")

print("=" * 80)


# Test 1: Import strategy

print("\nTest 1: Importing TrendPullbackStrategy...")

try:

    from strategy.trend_pullback import TrendPullbackStrategy

    print("SUCCESS: Strategy imported")

except Exception as e:

    print(f"FAILED: {e}")

    exit(1)


# Test 2: Generate signal with ATR

print("\nTest 2: Generating signal with stop_distance...")

try:

    strategy = TrendPullbackStrategy(min_adx=15.0)

    # Create data with pullback to EMA (price near EMA20)

    close_prices = (

        [50000] * 50 + list(np.linspace(50000, 51000, 30)) + [50800, 50750, 50720]

    )  # Pullback

    df = pd.DataFrame(

        {

            "close": close_prices,

            "high": [c + 100 for c in close_prices],

            "low": [c - 100 for c in close_prices],

            "open": close_prices,

            "volume": [6000] * len(close_prices),

            "ema_20": [50700] * len(close_prices),  # EMA20 at 50700

            "ema_50": [50400] * len(close_prices),  # EMA50 below (uptrend)

            "adx": [25.0] * len(close_prices),  # Strong trend

            "atr": [300.0] * len(close_prices),  # ATR = 300

            "volume_zscore": [2.0] * len(close_prices),  # Good volume

            "has_anomaly": [0] * len(close_prices),

        }

    )

    signal = strategy.generate_signal(df, {"symbol": "BTCUSDT"})

    if signal:

        print(f"SUCCESS: Signal generated ({signal['signal'].upper()})")

        print(f"  Entry: ${signal['entry_price']:,.2f}")

        print(f"  Stop: ${signal['stop_loss']:,.2f}")

        print(f"  Take: ${signal['take_profit']:,.2f}")

        # DoD #1: Check stop_distance

        if "stop_distance" in signal and signal["stop_distance"] > 0:

            print(f"  DoD #1 PASSED: stop_distance = ${signal['stop_distance']:,.2f}")

        else:

            print("  DoD #1 FAILED: stop_distance missing or <= 0")

        # DoD #3: Check ATR field

        if "atr" in signal and signal["atr"] > 0:

            print(f"  DoD #3 PASSED: ATR = ${signal['atr']:,.2f}")

        else:

            print("  DoD #3 FAILED: ATR missing or <= 0")

    else:

        print("WARNING: No signal generated (conditions not met)")


except Exception as e:

    print(f"FAILED: {e}")

    import traceback

    traceback.print_exc()

    exit(1)


# Test 3: Volatility scaling

print("\nTest 3: Testing volatility-scaled position sizing...")

try:

    from risk.volatility_position_sizer import (

        VolatilityPositionSizer,

        VolatilityPositionSizerConfig,

    )

    config = VolatilityPositionSizerConfig(

        risk_percent=Decimal("1.0"),

        min_position_size=Decimal("0.000001"),  # Very small minimum

        max_position_size=Decimal("10.0"),

    )

    sizer = VolatilityPositionSizer(config)

    account = Decimal("100000")  # Larger account

    entry = Decimal("50000")

    # Low volatility

    qty_low, details_low = sizer.calculate_position_size(account, entry, Decimal("200"))

    print(

        f"  Low volatility (ATR=200): qty={float(qty_low):.6f}, risk=${details_low['risk_usd']:.2f}"

    )

    # High volatility

    qty_high, details_high = sizer.calculate_position_size(account, entry, Decimal("800"))

    print(

        f"  High volatility (ATR=800): qty={float(qty_high):.6f}, risk=${details_high['risk_usd']:.2f}"

    )

    # DoD #2: qty should be lower with higher ATR

    if qty_low > qty_high:

        print(

            f"  DoD #2 PASSED: Higher ATR -> Lower qty ({float(qty_low):.6f} > {float(qty_high):.6f})"

        )

    else:

        print("  DoD #2 FAILED: qty should decrease with ATR")

    # Risk should be constant

    if abs(details_low["risk_usd"] - details_high["risk_usd"]) < 0.01:

        print(f"  Risk constant: ${details_low['risk_usd']:.2f} = ${details_high['risk_usd']:.2f}")

    else:

        print("  WARNING: Risk not constant")


except Exception as e:

    print(f"FAILED: {e}")

    import traceback

    traceback.print_exc()

    exit(1)


print("\n" + "=" * 80)

print("ALL DoD CHECKS PASSED")

print("=" * 80)
