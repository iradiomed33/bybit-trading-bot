# coding: utf-8

"""

Debug: Liquidation wick detection

"""


import pandas as pd

from data.features import FeaturePipeline


pipeline = FeaturePipeline()


# Создаем экстремальную ликвидационную свечу

df = pd.DataFrame(

    {

        "close": [50000, 50000, 48500, 50000, 50000],  # #2 - большое движение

        "high": [50100, 50100, 51500, 50100, 50100],  # #2 - огромная верхняя тень (3000 вверх)

        "low": [49900, 49900, 48000, 49900, 49900],  # #2 - огромная нижняя тень (500 вниз)

        "open": [50000, 50000, 50000, 50000, 50000],

        "volume": [1000, 1000, 15000, 1000, 1000],  # #2 - огромный всплеск объёма (15x)

    }

)


df["atr"] = 300.0  # ATR = 300


print("Before detection:")

print(df[["close", "high", "low", "volume"]])


# Детектируем

df = pipeline.detect_liquidation_wicks(

    df,

    atr_multiplier=2.5,  # Range > 2.5 * 300 = 750

    wick_ratio_threshold=0.7,  # Wick > 70% of range

    volume_percentile=95.0,  # Volume > 95th percentile

)


print("\nAfter detection:")

print(df[["liquidation_wick", "candle_range_atr", "wick_ratio", "volume"]])


print(f"\nLiquidation wicks detected: {df['liquidation_wick'].sum()}")


# Проверяем свечу #2 вручную

candle_2 = df.iloc[2]

candle_range = candle_2["high"] - candle_2["low"]

body = abs(candle_2["close"] - candle_2["open"])

upper_wick = candle_2["high"] - max(candle_2["close"], candle_2["open"])

lower_wick = min(candle_2["close"], candle_2["open"]) - candle_2["low"]

max_wick = max(upper_wick, lower_wick)


print("\nCandle #2 details:")

print(f"  Range: {candle_range} (ATR: {candle_2['atr']})")

print(f"  Range/ATR: {candle_range / candle_2['atr']:.2f}x (threshold: 2.5x)")

print(f"  Body: {body}")

print(f"  Upper wick: {upper_wick}")

print(f"  Lower wick: {lower_wick}")

print(f"  Max wick: {max_wick}")

print(f"  Wick ratio: {max_wick / candle_range:.2f} (threshold: 0.70)")

print(f"  Volume: {candle_2['volume']}")

print(f"  Volume 95th pctl: {df['volume'].quantile(0.95)}")
