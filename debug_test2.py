import pandas as pd

from strategy.breakout import BreakoutStrategy

from logger import setup_logger


# Enable debug logging

logger = setup_logger(__name__)

logger.setLevel("DEBUG")


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

        }

    )

    return df


df = create_test_df()


strategy = BreakoutStrategy(

    bb_width_threshold=0.02, min_volume_zscore=1.5, min_atr_percent_expansion=1.0

)


print("Running generate_signal...")

signal = strategy.generate_signal(df, {"symbol": "TEST", "spread_percent": 0.1})

print(f"Signal: {signal}")
