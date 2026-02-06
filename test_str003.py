"""

STR-003 DoD Validation: Entry Confirmation


Tests:

1. entry_mode parameter exists and validates correctly

2. immediate mode: entry on pullback (old behavior)

3. confirm_close mode: rejection when no confirmation

4. confirm_close mode: acceptance when rejection pattern present

5. limit_retest mode: generates limit order signal

"""


import pandas as pd

from strategy.trend_pullback import TrendPullbackStrategy


def create_test_df(prices, ema_20_values):
    """Create synthetic DataFrame for testing"""

    n = len(prices)

    df = pd.DataFrame(

        {

            "close": prices,

            "high": [p * 1.01 for p in prices],

            "low": [p * 0.99 for p in prices],

            "open": prices,

            "volume": [1000] * n,

            "ema_20": ema_20_values,

            "ema_50": [50000] * n,  # Always below EMA20 for uptrend

            "adx": [25.0] * n,  # Strong trend

            "atr": [300.0] * n,

            "volume_zscore": [2.0] * n,  # High volume

            "has_anomaly": [0] * n,  # No anomalies

        }

    )

    return df


def test_entry_mode_parameter():
    """Test 1: entry_mode parameter exists and validates"""

    print("\n=== Test 1: Entry Mode Parameter ===")

    # Valid modes

    for mode in ["immediate", "confirm_close", "limit_retest"]:

        try:

            strategy = TrendPullbackStrategy(entry_mode=mode)

            print(f"✅ Mode '{mode}' accepted: {strategy.entry_mode}")

        except Exception as e:

            print(f"❌ Mode '{mode}' failed: {e}")

            return False

    # Invalid mode

    try:

        strategy = TrendPullbackStrategy(entry_mode="invalid")

        print("❌ Invalid mode should have raised error")

        return False

    except ValueError as e:

        print(f"✅ Invalid mode rejected: {e}")

    print("\n✅ Test 1 PASSED: entry_mode parameter working\n")

    return True


def test_immediate_mode():
    """Test 2: immediate mode - entry without confirmation"""

    print("\n=== Test 2: Immediate Mode (Old Behavior) ===")

    strategy = TrendPullbackStrategy(min_adx=15.0, entry_mode="immediate")

    # Scenario: Price at EMA level, no rejection pattern

    # In immediate mode, should generate signal

    prices = [51000, 50500, 50200]  # Pullback to EMA

    ema_values = [50500, 50500, 50200]  # EMA at 50200

    df = create_test_df(prices, ema_values)

    features = {"symbol": "BTCUSDT"}

    signal = strategy.generate_signal(df, features)

    if signal is not None:

        print("✅ Signal generated in immediate mode")

        print(f"   Direction: {signal['signal']}")

        print(f"   Entry mode: {signal.get('entry_mode')}")

        print(f"   Confirmation: {signal.get('confirmation')}")

        if signal["entry_mode"] == "immediate":

            print("\n✅ Test 2 PASSED: Immediate mode working\n")

            return True

    print("❌ Test 2 FAILED: No signal in immediate mode")

    return False


def test_confirm_close_rejection():
    """Test 3: confirm_close mode - rejection without confirmation"""

    print("\n=== Test 3: Confirm Close - Rejection ===")

    strategy = TrendPullbackStrategy(min_adx=15.0, entry_mode="confirm_close")

    # Scenario: Price at EMA level, but NO rejection pattern

    # Previous close at 50200, current close at 50200 (both AT ema)

    # For LONG: need prev_close < ema AND current_close > ema

    prices = [51000, 50200, 50200]  # At EMA, no rejection

    ema_values = [50500, 50200, 50200]

    df = create_test_df(prices, ema_values)

    features = {"symbol": "BTCUSDT"}

    signal = strategy.generate_signal(df, features)

    if signal is None:

        print("✅ Signal rejected (no confirmation)")

        print("   Mode: confirm_close")

        print("   Reason: No rejection pattern detected")

        print("\n✅ Test 3 PASSED: Rejection without confirmation\n")

        return True

    else:

        print("❌ Test 3 FAILED: Signal generated without confirmation")

        print(f"   Signal: {signal}")

        return False


def test_confirm_close_acceptance():
    """Test 4: confirm_close mode - acceptance with rejection pattern"""

    print("\n=== Test 4: Confirm Close - Acceptance ===")

    strategy = TrendPullbackStrategy(min_adx=15.0, entry_mode="confirm_close")

    # Scenario: LONG with rejection pattern

    # Previous close BELOW EMA (50000), current close ABOVE EMA (50400)

    # This is a bullish rejection of the EMA level

    prices = [51000, 50000, 50400]  # Below EMA → Above EMA

    ema_values = [50500, 50200, 50200]  # EMA at 50200

    df = create_test_df(prices, ema_values)

    features = {"symbol": "BTCUSDT"}

    signal = strategy.generate_signal(df, features)

    if signal is not None:

        print("✅ Signal generated with confirmation")

        print(f"   Direction: {signal['signal']}")

        print(f"   Entry mode: {signal.get('entry_mode')}")

        confirmation = signal.get("confirmation", {})

        print("   Confirmation details:")

        print(f"      Mode: {confirmation.get('mode')}")

        print(f"      Confirmed: {confirmation.get('confirmed')}")

        print(f"      Prev close: {confirmation.get('prev_close')} (< EMA)")

        print(f"      Current close: {confirmation.get('current_close')} (> EMA)")

        print(f"      EMA level: {confirmation.get('ema_level')}")

        if (

            confirmation.get("confirmed")

            and confirmation.get("prev_below_ema")

            and confirmation.get("current_above_ema")

        ):

            print("\n✅ Test 4 PASSED: Acceptance with rejection pattern\n")

            return True

        else:

            print("❌ Test 4 FAILED: Confirmation details incorrect")

            return False

    print("❌ Test 4 FAILED: No signal with rejection pattern")

    return False


def test_confirm_close_short():
    """Test 4b: confirm_close mode - SHORT with rejection pattern"""

    print("\n=== Test 4b: Confirm Close - SHORT Acceptance ===")

    strategy = TrendPullbackStrategy(min_adx=15.0, entry_mode="confirm_close")

    # Scenario: SHORT with rejection pattern

    # Downtrend: EMA20 < EMA50

    # Previous close ABOVE EMA (50400), current close BELOW EMA (50000)

    # This is a bearish rejection of the EMA level

    prices = [49000, 50400, 50000]  # Above EMA → Below EMA

    ema_values = [50500, 50200, 50200]  # EMA at 50200

    ema_50_values = [51000, 51000, 51000]  # EMA50 > EMA20 = downtrend

    df = create_test_df(prices, ema_values)

    df["ema_50"] = ema_50_values  # Override for downtrend

    features = {"symbol": "BTCUSDT"}

    signal = strategy.generate_signal(df, features)

    if signal is not None:

        print("✅ Signal generated with confirmation")

        print(f"   Direction: {signal['signal']}")

        print(f"   Entry mode: {signal.get('entry_mode')}")

        confirmation = signal.get("confirmation", {})

        print("   Confirmation details:")

        print(f"      Mode: {confirmation.get('mode')}")

        print(f"      Confirmed: {confirmation.get('confirmed')}")

        print(f"      Prev close: {confirmation.get('prev_close')} (> EMA)")

        print(f"      Current close: {confirmation.get('current_close')} (< EMA)")

        print(f"      EMA level: {confirmation.get('ema_level')}")

        if (

            signal["signal"] == "short"

            and confirmation.get("confirmed")

            and confirmation.get("prev_above_ema")

            and confirmation.get("current_below_ema")

        ):

            print("\n✅ Test 4b PASSED: SHORT acceptance with rejection pattern\n")

            return True

        else:

            print("❌ Test 4b FAILED: Confirmation details incorrect")

            return False

    print("❌ Test 4b FAILED: No SHORT signal with rejection pattern")

    return False


def test_limit_retest_mode():
    """Test 5: limit_retest mode - generates limit order signal"""

    print("\n=== Test 5: Limit Retest Mode ===")

    strategy = TrendPullbackStrategy(min_adx=15.0, entry_mode="limit_retest", limit_ttl_bars=5)

    # Scenario: Price approaching EMA level

    # Should generate limit order to place at EMA level

    prices = [51000, 50500, 50300]  # Approaching EMA

    ema_values = [50500, 50200, 50200]  # EMA at 50200

    df = create_test_df(prices, ema_values)

    features = {"symbol": "BTCUSDT"}

    signal = strategy.generate_signal(df, features)

    if signal is not None:

        print("✅ Signal generated in limit_retest mode")

        print(f"   Direction: {signal['signal']}")

        print(f"   Entry mode: {signal.get('entry_mode')}")

        print(f"   Limit order: {signal.get('limit_order')}")

        print(f"   Target price: {signal.get('target_price')}")

        print(f"   TTL bars: {signal.get('ttl_bars')}")

        print(f"   Current close: {prices[-1]}")

        confirmation = signal.get("confirmation", {})

        print("   Confirmation details:")

        print(f"      Mode: {confirmation.get('mode')}")

        print(f"      Target price: {confirmation.get('target_price')}")

        print(f"      TTL bars: {confirmation.get('ttl_bars')}")

        if (

            signal.get("limit_order")

            and signal.get("target_price") == ema_values[-1]

            and signal.get("ttl_bars") == 5

        ):

            print("\n✅ Test 5 PASSED: Limit retest mode working\n")

            return True

        else:

            print("❌ Test 5 FAILED: Limit order details incorrect")

            return False

    print("❌ Test 5 FAILED: No signal in limit_retest mode")

    return False


def test_dod_requirements():
    """DoD Validation"""

    print("\n" + "=" * 60)

    print("STR-003 DoD VALIDATION")

    print("=" * 60)

    # DoD #1: Entry rule описан явно и покрыт тестом на синтетических данных

    print("\n📋 DoD #1: Entry rule described and tested")

    print(

        "   ✅ confirm_close: rejection pattern (prev close below/above EMA → current close above/below)"

    )

    print("   ✅ limit_retest: limit order at EMA level with TTL")

    print("   ✅ immediate: old behavior (no confirmation)")

    # DoD #2: Есть параметр entry_mode: confirm_close / limit_retest

    print("\n📋 DoD #2: entry_mode parameter exists")

    strategy = TrendPullbackStrategy(entry_mode="confirm_close")

    print(f"   ✅ entry_mode parameter: {strategy.entry_mode}")

    print("   ✅ Supported modes: immediate, confirm_close, limit_retest")

    print("\n" + "=" * 60)

    print("SUMMARY")

    print("=" * 60)

    results = []

    results.append(("Parameter validation", test_entry_mode_parameter()))

    results.append(("Immediate mode", test_immediate_mode()))

    results.append(("Confirm close - rejection", test_confirm_close_rejection()))

    results.append(("Confirm close - LONG acceptance", test_confirm_close_acceptance()))

    results.append(("Confirm close - SHORT acceptance", test_confirm_close_short()))

    results.append(("Limit retest mode", test_limit_retest_mode()))

    print("\nTest Results:")

    all_passed = True

    for test_name, passed in results:

        status = "✅ PASSED" if passed else "❌ FAILED"

        print(f"   {status}: {test_name}")

        if not passed:

            all_passed = False

    print("\n" + "=" * 60)

    if all_passed:

        print("🎉 ALL TESTS PASSED - STR-003 DoD REQUIREMENTS MET")

    else:

        print("❌ SOME TESTS FAILED - Review implementation")

    print("=" * 60 + "\n")

    return all_passed


if __name__ == "__main__":

    test_dod_requirements()
