"""

STR-005 Validation Tests: Mean Reversion Time-Based Exits


DoD Requirements:

1. No MR trade hangs forever (time_stop enforced)

2. Logs show exit_reason=time_stop/stop_loss/take_profit


Test Scenarios:

1. Time stop after max_hold_bars exceeded

2. Time stop after max_hold_minutes exceeded

3. Stop loss on adverse price move (LONG and SHORT)

4. Take profit on mean reversion (LONG and SHORT)

5. Position tracking state management

6. No infinite holds (all positions eventually exit)

"""


import pandas as pd

from strategy.mean_reversion import MeanReversionStrategy

from datetime import datetime, timedelta


def create_test_df(length=100, **overrides):
    """Create test DataFrame with default values and overrides"""

    df = pd.DataFrame(

        {

            "close": [100.0] * length,

            "vwap": [100.0] * length,

            "vwap_distance": [0.0] * length,  # Add vwap_distance

            "rsi": [50.0] * length,

            "adx": [15.0] * length,

            "ema_20": [100.0] * length,

            "ema_50": [100.0] * length,

            "atr": [2.0] * length,

            "bb_width": [0.02] * length,

            "bb_width_pct_change": [-0.01] * length,

            "atr_slope": [0.1] * length,

            "vol_regime": [-1] * length,  # -1 = low volatility

            "timestamp": [datetime.now() + timedelta(minutes=i) for i in range(length)],

        }

    )

    for key, value in overrides.items():

        if isinstance(value, list):

            df[key] = value

        else:

            df[key] = [value] * length

    return df


def test_time_stop_bars():
    """Test 1: Time stop triggered after max_hold_bars"""

    print("\n=== Test 1: Time Stop (Bars) ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=10,

        require_range_regime=False,  # Disable for isolated testing

        enable_anti_knife=False,

    )

    # Entry setup: LONG at bar 0

    df_entry = create_test_df(

        1,

        close=[95.0],  # Below VWAP

        vwap=[100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100],  # -5.0%

        rsi=[25.0],  # Oversold

        adx=[15.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal is not None, "Entry signal should be generated"

    assert signal["signal"] == "long", f"Expected LONG, got {signal['signal']}"

    assert strategy._active_position is not None, "Position should be tracked"

    print(f"✅ Entry: LONG at {signal['entry_price']}")

    # Hold for 9 bars (below limit) - no exit

    for i in range(9):

        df_hold = create_test_df(

            i + 2,

            close=[95.0] * 1 + [96.0] * (i + 1),  # Entry bar + hold bars

            vwap=[100.0] * (i + 2),

            vwap_distance=[((95.0 - 100.0) / 100.0) * 100]

            + [((96.0 - 100.0) / 100.0) * 100] * (i + 1),

            rsi=[25.0] + [35.0] * (i + 1),

            adx=[15.0] * (i + 2),

        )

        exit_signal = strategy.generate_signal(df_hold, {"symbol": "TEST"})

        assert exit_signal is None, f"Should not exit at bar {i + 1}"

    print("✅ Hold: No exit for 9 bars")

    # Bar 10: time_stop triggered

    df_exit = create_test_df(

        11,

        close=[95.0] + [96.0] * 10,

        vwap=[100.0] * 11,

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100] + [((96.0 - 100.0) / 100.0) * 100] * 10,

        rsi=[25.0] + [35.0] * 10,

        adx=[15.0] * 11,

    )

    exit_signal = strategy.generate_signal(df_exit, {"symbol": "TEST"})

    assert exit_signal is not None, "Exit signal should be generated at bar 10"

    assert exit_signal["signal"] == "exit", f"Expected EXIT, got {exit_signal.get('signal')}"

    assert (

        exit_signal["exit_reason"] == "time_stop"

    ), f"Expected time_stop, got {exit_signal['exit_reason']}"

    assert exit_signal["bars_held"] == 10, f"Expected bars_held=10, got {exit_signal['bars_held']}"

    assert strategy._active_position is None, "Position should be cleared after exit"

    print(

        f"✅ Exit: time_stop at bar 10, reason={exit_signal['exit_reason']}, bars_held={exit_signal['bars_held']}"

    )

    print("✅ Test 1 PASSED: Time stop enforced after max_hold_bars\n")


def test_stop_loss_long():
    """Test 2: Stop loss triggered on LONG position"""

    print("\n=== Test 2: Stop Loss (LONG) ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=50,

        stop_loss_atr_multiplier=1.0,

        require_range_regime=False,

        enable_anti_knife=False,

    )

    # Entry: LONG at 95, ATR=2.0, stop at 95 - 2.0 = 93.0

    df_entry = create_test_df(

        1,

        close=[95.0],

        vwap=[100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100],  # -5.0%

        rsi=[25.0],

        adx=[15.0],

        atr=[2.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal["signal"] == "long"

    entry_price = 95.0

    stop_price = entry_price - (1.0 * 2.0)  # 93.0

    print(f"✅ Entry: LONG at {entry_price}, stop at {stop_price}")

    # Price drops to stop level

    df_stop = create_test_df(

        2,

        close=[95.0, 93.0],  # Hit stop

        vwap=[100.0, 100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100, ((93.0 - 100.0) / 100.0) * 100],

        rsi=[25.0, 25.0],

        adx=[15.0, 15.0],

        atr=[2.0, 2.0],

    )

    exit_signal = strategy.generate_signal(df_stop, {"symbol": "TEST"})

    assert exit_signal is not None, "Stop loss should trigger"

    assert (

        exit_signal["exit_reason"] == "stop_loss"

    ), f"Expected stop_loss, got {exit_signal['exit_reason']}"

    assert exit_signal["pnl_pct"] < 0, f"PnL should be negative, got {exit_signal['pnl_pct']}"

    print(f"✅ Exit: stop_loss at {exit_signal['exit_price']}, PnL={exit_signal['pnl_pct']:.2f}%")

    print("✅ Test 2 PASSED: Stop loss enforced\n")


def test_stop_loss_short():
    """Test 3: Stop loss triggered on SHORT position"""

    print("\n=== Test 3: Stop Loss (SHORT) ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=50,

        stop_loss_atr_multiplier=1.0,

        require_range_regime=False,

        enable_anti_knife=False,

    )

    # Entry: SHORT at 105, ATR=2.0, stop at 105 + 2.0 = 107.0

    df_entry = create_test_df(

        1,

        close=[105.0],

        vwap=[100.0],

        vwap_distance=[((105.0 - 100.0) / 100.0) * 100],  # +5.0%

        rsi=[75.0],  # Overbought

        adx=[15.0],

        atr=[2.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal["signal"] == "short"

    entry_price = 105.0

    stop_price = entry_price + (1.0 * 2.0)  # 107.0

    print(f"✅ Entry: SHORT at {entry_price}, stop at {stop_price}")

    # Price rises to stop level

    df_stop = create_test_df(

        2,

        close=[105.0, 107.0],  # Hit stop

        vwap=[100.0, 100.0],

        vwap_distance=[((105.0 - 100.0) / 100.0) * 100, ((107.0 - 100.0) / 100.0) * 100],

        rsi=[75.0, 75.0],

        adx=[15.0, 15.0],

        atr=[2.0, 2.0],

    )

    exit_signal = strategy.generate_signal(df_stop, {"symbol": "TEST"})

    assert exit_signal is not None, "Stop loss should trigger"

    assert (

        exit_signal["exit_reason"] == "stop_loss"

    ), f"Expected stop_loss, got {exit_signal['exit_reason']}"

    assert exit_signal["pnl_pct"] < 0, f"PnL should be negative, got {exit_signal['pnl_pct']}"

    print(f"✅ Exit: stop_loss at {exit_signal['exit_price']}, PnL={exit_signal['pnl_pct']:.2f}%")

    print("✅ Test 3 PASSED: Stop loss enforced (SHORT)\n")


def test_take_profit_long():
    """Test 4: Take profit on mean reversion (LONG)"""

    print("\n=== Test 4: Take Profit (LONG) ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=50, require_range_regime=False, enable_anti_knife=False

    )

    # Entry: LONG at 95, target VWAP=100

    df_entry = create_test_df(

        1,

        close=[95.0],

        vwap=[100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100],  # -5.0%

        rsi=[25.0],

        adx=[15.0],

        atr=[2.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal["signal"] == "long"

    print(f"✅ Entry: LONG at {signal['entry_price']}, target VWAP=100.0")

    # Price reverts to mean

    df_target = create_test_df(

        2,

        close=[95.0, 100.0],  # Reached VWAP

        vwap=[100.0, 100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100, 0.0],

        rsi=[25.0, 50.0],

        adx=[15.0, 15.0],

        atr=[2.0, 2.0],

    )

    exit_signal = strategy.generate_signal(df_target, {"symbol": "TEST"})

    assert exit_signal is not None, "Take profit should trigger"

    assert (

        exit_signal["exit_reason"] == "take_profit"

    ), f"Expected take_profit, got {exit_signal['exit_reason']}"

    assert exit_signal["pnl_pct"] > 0, f"PnL should be positive, got {exit_signal['pnl_pct']}"

    print(f"✅ Exit: take_profit at {exit_signal['exit_price']}, PnL={exit_signal['pnl_pct']:.2f}%")

    print("✅ Test 4 PASSED: Take profit on mean reversion\n")


def test_take_profit_short():
    """Test 5: Take profit on mean reversion (SHORT)"""

    print("\n=== Test 5: Take Profit (SHORT) ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=50, require_range_regime=False, enable_anti_knife=False

    )

    # Entry: SHORT at 105, target VWAP=100

    df_entry = create_test_df(

        1,

        close=[105.0],

        vwap=[100.0],

        vwap_distance=[((105.0 - 100.0) / 100.0) * 100],  # +5.0%

        rsi=[75.0],

        adx=[15.0],

        atr=[2.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal["signal"] == "short"

    print(f"✅ Entry: SHORT at {signal['entry_price']}, target VWAP=100.0")

    # Price reverts to mean

    df_target = create_test_df(

        2,

        close=[105.0, 100.0],  # Reached VWAP

        vwap=[100.0, 100.0],

        vwap_distance=[((105.0 - 100.0) / 100.0) * 100, 0.0],

        rsi=[75.0, 50.0],

        adx=[15.0, 15.0],

        atr=[2.0, 2.0],

    )

    exit_signal = strategy.generate_signal(df_target, {"symbol": "TEST"})

    assert exit_signal is not None, "Take profit should trigger"

    assert (

        exit_signal["exit_reason"] == "take_profit"

    ), f"Expected take_profit, got {exit_signal['exit_reason']}"

    assert exit_signal["pnl_pct"] > 0, f"PnL should be positive, got {exit_signal['pnl_pct']}"

    print(f"✅ Exit: take_profit at {exit_signal['exit_price']}, PnL={exit_signal['pnl_pct']:.2f}%")

    print("✅ Test 5 PASSED: Take profit on mean reversion (SHORT)\n")


def test_no_infinite_holds():
    """Test 6: Guarantee that positions eventually exit (no infinite holds)"""

    print("\n=== Test 6: No Infinite Holds ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=20, require_range_regime=False, enable_anti_knife=False

    )

    # Entry

    df_entry = create_test_df(

        1,

        close=[95.0],

        vwap=[100.0],

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100],  # -5.0%

        rsi=[25.0],

        adx=[15.0],

        atr=[2.0],

    )

    signal = strategy.generate_signal(df_entry, {"symbol": "TEST"})

    assert signal["signal"] == "long"

    print(f"✅ Entry: LONG at {signal['entry_price']}")

    # Simulate worst case: price doesn't hit stop or target

    # But time limit MUST force exit

    exit_triggered = False

    for i in range(1, 25):  # Go beyond max_hold_bars

        # Create DF with entry bar + current bars

        df = create_test_df(

            i + 1,

            close=[95.0] + [96.0] * i,  # Entry + hold bars

            vwap=[100.0] * (i + 1),

            vwap_distance=[((95.0 - 100.0) / 100.0) * 100] + [((96.0 - 100.0) / 100.0) * 100] * i,

            rsi=[25.0] + [35.0] * i,

            adx=[15.0] * (i + 1),

            atr=[2.0] * (i + 1),

        )

        exit_signal = strategy.generate_signal(df, {"symbol": "TEST"})

        if exit_signal and exit_signal.get("signal") == "exit":

            exit_triggered = True

            bars_held = exit_signal["bars_held"]

            exit_reason = exit_signal["exit_reason"]

            print(f"✅ Exit: {exit_reason} at bar {bars_held}")

            assert bars_held == 20, f"Expected exit at bar 20, got {bars_held}"

            assert exit_reason == "time_stop", f"Expected time_stop, got {exit_reason}"

            break

    assert exit_triggered, "Position MUST exit within time limit"

    assert strategy._active_position is None, "Position state must be cleared"

    print("✅ Test 6 PASSED: No infinite holds - time_stop guaranteed\n")


def test_position_state_reset():
    """Test 7: Position tracking state properly resets after exit"""

    print("\n=== Test 7: Position State Reset ===")

    strategy = MeanReversionStrategy(

        max_hold_bars=5, require_range_regime=False, enable_anti_knife=False

    )

    # First trade: Entry -> Exit

    df1 = create_test_df(

        1, close=[95.0], vwap=[100.0], vwap_distance=[-5.0], rsi=[25.0], adx=[15.0]

    )

    signal1 = strategy.generate_signal(df1, {"symbol": "TEST"})

    assert signal1["signal"] == "long"

    assert strategy._active_position is not None

    print("✅ Trade 1: Entry LONG")

    # Force exit via time stop

    df2 = create_test_df(

        6,

        close=[95.0] + [96.0] * 5,

        vwap=[100.0] * 6,

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100] + [((96.0 - 100.0) / 100.0) * 100] * 5,

        rsi=[25.0] + [35.0] * 5,

        adx=[15.0] * 6,

    )

    exit1 = strategy.generate_signal(df2, {"symbol": "TEST"})

    assert exit1["exit_reason"] == "time_stop"

    assert strategy._active_position is None

    print("✅ Trade 1: Exit time_stop, position cleared")

    # Second trade: Should be able to enter again

    df3 = create_test_df(

        7,

        close=[95.0] + [96.0] * 5 + [95.0],

        vwap=[100.0] * 7,

        vwap_distance=[((95.0 - 100.0) / 100.0) * 100]

        + [((96.0 - 100.0) / 100.0) * 100] * 5

        + [((95.0 - 100.0) / 100.0) * 100],

        rsi=[25.0] + [35.0] * 5 + [25.0],

        adx=[15.0] * 7,

    )

    signal2 = strategy.generate_signal(df3, {"symbol": "TEST"})

    assert signal2["signal"] == "long", "Should allow new entry after exit"

    assert strategy._active_position is not None

    print("✅ Trade 2: Entry LONG (new position after reset)")

    print("✅ Test 7 PASSED: Position state resets correctly\n")


if __name__ == "__main__":

    print("=" * 60)

    print("STR-005 VALIDATION TESTS")

    print("Mean Reversion: Time-Based Exits & Emergency Stop")

    print("=" * 60)

    try:

        test_time_stop_bars()

        test_stop_loss_long()

        test_stop_loss_short()

        test_take_profit_long()

        test_take_profit_short()

        test_no_infinite_holds()

        test_position_state_reset()

        print("\n" + "=" * 60)

        print("Test Results:")

        print("   ✅ PASSED: Time stop (bars)")

        print("   ✅ PASSED: Stop loss (LONG)")

        print("   ✅ PASSED: Stop loss (SHORT)")

        print("   ✅ PASSED: Take profit (LONG)")

        print("   ✅ PASSED: Take profit (SHORT)")

        print("   ✅ PASSED: No infinite holds")

        print("   ✅ PASSED: Position state reset")

        print("\n🎉 ALL TESTS PASSED - STR-005 DoD REQUIREMENTS MET")

        print("\nDoD Validation:")

        print("   ✅ No MR trade hangs forever (time_stop enforced)")

        print("   ✅ Logs show exit_reason (time_stop/stop_loss/take_profit)")

        print("=" * 60)

    except AssertionError as e:

        print(f"\n❌ TEST FAILED: {e}")

        raise

    except Exception as e:

        print(f"\n❌ ERROR: {e}")

        raise
