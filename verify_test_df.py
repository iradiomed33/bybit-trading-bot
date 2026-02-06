import pandas as pd


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

            "atr_percent": [0.026 if atr_expand_ok else 0.015] * length,

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


df = create_test_df(

    151,

    bb_tight=True,

    squeeze_ok=True,

    expansion_ok=True,

    volume_ok=True,

    atr_expand_ok=True,

    breakout_up=True,

)


latest = df.iloc[-1]

print("Latest row:")

print(f'  bb_width_percentile: {latest["bb_width_percentile"]}')

print(f'  atr_percentile: {latest["atr_percentile"]}')

print(f'  bb_expansion: {latest["bb_expansion"]}')

print(f'  atr_expansion: {latest["atr_expansion"]}')

print(f'  volume_percentile: {latest["volume_percentile"]}')

print(f'  volume_ratio: {latest["volume_ratio"]}')
