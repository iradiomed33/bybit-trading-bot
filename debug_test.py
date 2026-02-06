import pandas as pd

from strategy.breakout import BreakoutStrategy


def create_test_df():

    df = pd.DataFrame(

        {

            "close": [100.0] * 150 + [103.0],

            "high": [101.0] * 151,

            "low": [99.0] * 151,

            "volume": [2000.0] * 151,

            "atr": [2.0] * 151,

            "atr_percent": [0.025] * 151,

            "bb_width": [0.015] * 151,

            "BBU_20_2.0": [102.0] * 151,

            "BBL_20_2.0": [98.0] * 151,

            "volume_zscore": [2.0] * 151,

            "bb_width_percentile": [1.0] * 151,

            "atr_percentile": [1.0] * 151,

            "bb_expansion": [1.0] * 151,

            "atr_expansion": [1.0] * 151,

            "volume_percentile": [1.0] * 151,

            "volume_sma": [1000.0] * 151,

            "volume_ratio": [2.0] * 151,

        }

    )

    return df


df = create_test_df()

latest = df.iloc[-1]

print("STR-006 Features in latest row:")

print(f'  bb_width_percentile: {latest.get("bb_width_percentile")}')

print(f'  atr_percentile: {latest.get("atr_percentile")}')

print(f'  bb_expansion: {latest.get("bb_expansion")}')

print(f'  atr_expansion: {latest.get("atr_expansion")}')

print(f'  volume_percentile: {latest.get("volume_percentile")}')

print(f'  volume_ratio: {latest.get("volume_ratio")}')

print()


# Check that we have a breakout

print("Breakout check:")

print(f"  prev_close: {df.iloc[-2]['close']}")

print(f"  curr_close: {df.iloc[-1]['close']}")

print(f"  prev_BBU: {df.iloc[-2]['BBU_20_2.0']}")

print(f"  curr_BBU: {df.iloc[-1]['BBU_20_2.0']}")

print(f"  BB columns: {[col for col in df.columns if 'BBU_' in col or 'BBL_' in col]}")

print()


strategy = BreakoutStrategy(

    require_squeeze=False,

    require_expansion=False,

    require_volume=False,

    min_atr_percent_expansion=1.0,

)


print("Running generate_signal...")

signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

print(f"Signal: {signal}")
