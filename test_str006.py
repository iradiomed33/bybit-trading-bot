"""

STR-006 Validation Tests: Breakout Squeeze → Expansion + Volume


DoD Requirements:

1. У breakout всегда есть "why": squeeze_ok, expansion_ok, volume_ok

2. Без объёма вход запрещён

"""


import pandas as pd

from strategy.breakout import BreakoutStrategy


def create_test_df(

    length,

    bb_tight=True,

    squeeze_ok=False,

    expansion_ok=False,

    volume_ok=False,

    atr_expand_ok=True,

    breakout_up=False,

):
    """Создать тестовый DataFrame"""

    close = [100.0] * (length - 1) + [103.0 if breakout_up else 97.0]

    bb_upper = [102.0] * length

    bb_lower = [98.0] * length

    df = pd.DataFrame(

        {

            "close": close,

            "high": [101.0] * length,

            "low": [99.0] * length,

            "volume": [2000.0 if volume_ok else 500.0] * length,

            "atr": [2.0] * length,

            "atr_percent": [0.026 if atr_expand_ok else 0.015]

            * length,  # 0.026 to avoid floating point comparison issues

            "bb_width": [0.015 if bb_tight else 0.04] * length,

            "BBU_20_2.0": bb_upper,

            "BBL_20_2.0": bb_lower,

            "volume_zscore": [2.0 if volume_ok else 0.5] * length,

            "bb_width_percentile": [1.0 if squeeze_ok else 0.0] * length,

            "atr_percentile": [1.0 if squeeze_ok else 0.0] * length,

            "bb_expansion": [1.0 if expansion_ok else 0.0] * length,

            "atr_expansion": [1.0 if expansion_ok else 0.0] * length,

            "volume_percentile": [1.0 if volume_ok else 0.0] * length,

            "volume_sma": [1000.0] * length,

            "volume_ratio": [2.0 if volume_ok else 0.8] * length,

        }

    )

    return df


def test_all_conditions_met():
    """Test 1: Squeeze + Expansion + Volume → Signal generated"""

    print("\n=== Test 1: All Conditions Met ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,

        min_atr_percent_expansion=1.0,

    )

    df = create_test_df(

        151,

        bb_tight=True,

        squeeze_ok=True,

        expansion_ok=True,

        volume_ok=True,

        atr_expand_ok=True,

        breakout_up=True,

    )

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is not None, "Signal should be generated"

    assert signal["signal"] == "long"

    reasons = signal["reasons"]

    values = signal["values"]

    assert "squeeze_ok" in reasons

    assert "expansion_ok" in reasons

    assert "volume_ok" in reasons

    assert values.get("squeeze_ok") is True

    assert values.get("expansion_ok") is True

    assert values.get("volume_ok") is True

    print("✅ LONG signal generated")

    print(f"✅ Reason: {signal['reason'][:50]}...")

    print("✅ Test 1 PASSED\n")


def test_no_squeeze_rejected():
    """Test 2: No squeeze → rejected"""

    print("\n=== Test 2: No Squeeze → Rejected ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,

        min_atr_percent_expansion=1.0,

    )

    # squeeze_ok=False

    df = create_test_df(151, squeeze_ok=False, expansion_ok=True, volume_ok=True, breakout_up=True)

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is None, "Signal should be rejected"

    print("✅ Rejected: no squeeze")

    print("✅ Test 2 PASSED\n")


def test_no_expansion_rejected():
    """Test 3: No expansion → rejected"""

    print("\n=== Test 3: No Expansion → Rejected ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,

        min_atr_percent_expansion=1.0,

    )

    df = create_test_df(151, squeeze_ok=True, expansion_ok=False, volume_ok=True, breakout_up=True)

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is None, "Signal should be rejected"

    print("✅ Rejected: no expansion")

    print("✅ Test 3 PASSED\n")


def test_no_volume_rejected_dod():
    """Test 4: No volume → rejected (DoD requirement)"""

    print("\n=== Test 4: No Volume → Rejected (DoD) ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,  # ОБЯЗАТЕЛЬНО для DoD

        min_atr_percent_expansion=1.0,

    )

    df = create_test_df(151, squeeze_ok=True, expansion_ok=True, volume_ok=False, breakout_up=True)

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is None, "Signal MUST be rejected without volume (DoD)"

    print("✅ Rejected: no volume (DoD requirement)")

    print("✅ Test 4 PASSED\n")


def test_short_breakout():
    """Test 5: SHORT breakout with all conditions"""

    print("\n=== Test 5: SHORT Breakout ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,

        min_atr_percent_expansion=1.0,

    )

    df = create_test_df(151, squeeze_ok=True, expansion_ok=True, volume_ok=True, breakout_up=False)

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is not None, "SHORT signal should be generated"

    assert signal["signal"] == "short"

    reasons = signal["reasons"]

    values = signal["values"]

    assert "squeeze_ok" in reasons

    assert "expansion_ok" in reasons

    assert "volume_ok" in reasons

    assert values.get("squeeze_ok") is True

    assert values.get("expansion_ok") is True

    assert values.get("volume_ok") is True

    print("✅ SHORT signal generated")

    print("✅ Reasons/values contain squeeze_ok, expansion_ok, volume_ok")

    print("✅ Test 5 PASSED\n")


def test_reasons_structure_dod():
    """Test 6: Reasons structure (DoD requirement)"""

    print("\n=== Test 6: Reasons Structure (DoD) ===")

    strategy = BreakoutStrategy(

        require_squeeze=True,

        require_expansion=True,

        require_volume=True,

        min_atr_percent_expansion=1.0,

    )

    df = create_test_df(151, squeeze_ok=True, expansion_ok=True, volume_ok=True, breakout_up=True)

    signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

    assert signal is not None

    reasons = signal["reasons"]

    values = signal["values"]

    # DoD: У breakout всегда есть "why"

    required_reasons = ["squeeze_ok", "expansion_ok", "volume_ok"]

    for req in required_reasons:

        assert req in reasons, f"{req} must be in reasons"

        assert req in values, f"{req} must be in values"

        assert values[req] is True, f"{req} must be True"

    print(f"✅ Required reasons present: {required_reasons}")

    print("✅ All metrics in values dict")

    print("✅ Test 6 PASSED\n")


if __name__ == "__main__":

    print("=" * 60)

    print("STR-006 VALIDATION TESTS")

    print("Breakout: Squeeze → Expansion + Volume Confirmation")

    print("=" * 60)

    try:

        test_all_conditions_met()

        test_no_squeeze_rejected()

        test_no_expansion_rejected()

        test_no_volume_rejected_dod()

        test_short_breakout()

        test_reasons_structure_dod()

        print("\n" + "=" * 60)

        print("Test Results:")

        print("   ✅ PASSED: All conditions met")

        print("   ✅ PASSED: No squeeze → rejected")

        print("   ✅ PASSED: No expansion → rejected")

        print("   ✅ PASSED: No volume → rejected (DoD)")

        print("   ✅ PASSED: SHORT breakout")

        print("   ✅ PASSED: Reasons structure (DoD)")

        print("\n🎉 ALL TESTS PASSED - STR-006 DoD REQUIREMENTS MET")

        print("\nDoD Validation:")

        print("   ✅ У breakout всегда есть 'why': squeeze_ok, expansion_ok, volume_ok")

        print("   ✅ Без объёма вход запрещён")

        print("=" * 60)

    except AssertionError as e:

        print(f"\n❌ TEST FAILED: {e}")

        raise

    except Exception as e:

        print(f"\n❌ ERROR: {e}")

        raise
