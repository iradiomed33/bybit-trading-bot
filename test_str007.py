"""

STR-007 Validation Tests: Breakout Retest Entry


Cases:

1) Retest within TTL confirms → signal.

2) TTL expires without retest → no signal, pending cleared.

3) Retest fails volume check → rejected.

4) Short breakout retest works.

"""


import pandas as pd

from strategy.breakout import BreakoutStrategy


FEATURES = {"symbol": "TEST", "spread_percent": 0.1}


def make_row(

    close: float,

    bb_upper: float,

    bb_lower: float,

    *,

    high: float | None = None,

    low: float | None = None,

    volume: float = 2000.0,

    volume_zscore: float = 2.0,

    atr: float = 2.0,

    atr_percent: float = 0.03,

    volume_percentile: float = 1.0,

    volume_ratio: float = 2.0,

    bb_width: float = 0.015,

    bb_width_percentile: float = 1.0,

    atr_percentile: float = 1.0,

    bb_expansion: float = 1.0,

    atr_expansion: float = 1.0,

):
    """Helper row for predictable inputs."""

    high_val = close if high is None else high

    low_val = close if low is None else low

    return {

        "close": close,

        "high": high_val,

        "low": low_val,

        "volume": volume,

        "atr": atr,

        "atr_percent": atr_percent,

        "bb_width": bb_width,

        "BBU_20_2.0": bb_upper,

        "BBL_20_2.0": bb_lower,

        "volume_zscore": volume_zscore,

        "bb_width_percentile": bb_width_percentile,

        "atr_percentile": atr_percentile,

        "bb_expansion": bb_expansion,

        "atr_expansion": atr_expansion,

        "volume_percentile": volume_percentile,

        "volume_ratio": volume_ratio,

    }


def test_retest_long_success():

    strategy = BreakoutStrategy(breakout_entry="retest", min_atr_percent_expansion=1.0)

    # Warm-up + breakout

    rows = [

        make_row(close=100.0, bb_upper=101.0, bb_lower=99.0),

        make_row(close=102.0, bb_upper=101.0, bb_lower=99.0, high=102.0, low=100.0),

    ]

    df = pd.DataFrame(rows)

    # Breakout should queue retest

    assert strategy.generate_signal(df, FEATURES) is None

    # Retest candle: low pierces level, close reclaims above

    rows.append(

        make_row(

            close=101.6,

            bb_upper=101.0,

            bb_lower=99.0,

            high=102.0,

            low=100.6,

            volume_zscore=2.2,

            volume_percentile=1.0,

            volume_ratio=2.0,

        )

    )

    df = pd.DataFrame(rows)

    signal = strategy.generate_signal(df, FEATURES)

    assert signal is not None, "Retest within TTL must emit signal"

    assert signal["signal"] == "long"

    assert "retest_confirmed" in signal["reasons"]

    assert "retest_entry" in signal["reasons"]

    assert signal["values"].get("breakout_entry") == "retest"

    assert signal["values"].get("retest_confirmed") is True

    assert signal["values"].get("retest_pending") is False


def test_retest_ttl_expired_no_signal():

    strategy = BreakoutStrategy(breakout_entry="retest", min_atr_percent_expansion=1.0)

    # Warm-up + breakout

    rows = [

        make_row(close=100.0, bb_upper=101.0, bb_lower=99.0),

        make_row(close=102.0, bb_upper=101.0, bb_lower=99.0, high=102.0, low=100.0),

    ]

    df = pd.DataFrame(rows)

    assert strategy.generate_signal(df, FEATURES) is None

    # Bars that do NOT retest the level until TTL expires

    for _ in range(strategy.retest_ttl_bars + 2):

        rows.append(

            make_row(

                close=102.5,

                bb_upper=101.0,

                bb_lower=99.0,

                high=103.0,

                low=102.0,

            )

        )

        df = pd.DataFrame(rows)

        strategy.generate_signal(df, FEATURES)

    # After TTL expiry, pending cleared; even if retest happens, no signal because no pending

    rows.append(

        make_row(

            close=101.4,

            bb_upper=101.0,

            bb_lower=99.0,

            high=102.0,

            low=100.5,

            volume_percentile=1.0,

            volume_ratio=2.0,

        )

    )

    df = pd.DataFrame(rows)

    signal = strategy.generate_signal(df, FEATURES)

    assert signal is None, "After TTL expiry retest must not fire"

    assert strategy._retest_pending is None


def test_retest_volume_rejected():

    strategy = BreakoutStrategy(breakout_entry="retest", min_atr_percent_expansion=1.0)

    rows = [

        make_row(close=100.0, bb_upper=101.0, bb_lower=99.0),

        make_row(close=102.0, bb_upper=101.0, bb_lower=99.0, high=102.0, low=100.0),

    ]

    df = pd.DataFrame(rows)

    assert strategy.generate_signal(df, FEATURES) is None

    # Retest without volume confirmation -> rejected

    rows.append(

        make_row(

            close=101.5,

            bb_upper=101.0,

            bb_lower=99.0,

            high=102.0,

            low=100.6,

            volume_percentile=0.0,

            volume_ratio=1.0,

        )

    )

    df = pd.DataFrame(rows)

    signal = strategy.generate_signal(df, FEATURES)

    assert signal is None, "Retest must fail without volume confirmation"


def test_retest_short_success():

    strategy = BreakoutStrategy(breakout_entry="retest", min_atr_percent_expansion=1.0)

    # Warm-up + breakout short

    rows = [

        make_row(close=100.0, bb_upper=101.0, bb_lower=99.0),

        make_row(close=97.0, bb_upper=101.0, bb_lower=99.0, high=100.0, low=97.0),

    ]

    df = pd.DataFrame(rows)

    assert strategy.generate_signal(df, FEATURES) is None

    # Retest: high wicks above level, close back below

    rows.append(

        make_row(

            close=98.5,

            bb_upper=101.0,

            bb_lower=99.0,

            high=99.4,

            low=98.0,

            volume_zscore=2.2,

            volume_percentile=1.0,

            volume_ratio=2.0,

        )

    )

    df = pd.DataFrame(rows)

    signal = strategy.generate_signal(df, FEATURES)

    assert signal is not None, "Short retest within TTL must emit signal"

    assert signal["signal"] == "short"

    assert "retest_confirmed" in signal["reasons"]

    assert "breakout_short" in signal["reasons"]

    assert signal["values"].get("retest_confirmed") is True

    assert signal["values"].get("retest_pending") is False


if __name__ == "__main__":

    test_retest_long_success()

    test_retest_ttl_expired_no_signal()

    test_retest_volume_rejected()

    test_retest_short_success()

    print("STR-007 tests executed")
