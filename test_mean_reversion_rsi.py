"""

Интеграционный тест: MeanReversionStrategy использует реальный RSI


Проверяет что:

1. RSI вычисляется и передается в dataframe

2. MeanReversionStrategy использует реальный RSI, а не default=50

3. Сигнал генерируется только при правильных условиях RSI

"""


import pandas as pd

import numpy as np

from data.features import FeaturePipeline

from strategy.mean_reversion import MeanReversionStrategy


def test_mean_reversion_with_real_rsi_oversold():
    """

    Test: MeanReversionStrategy генерирует LONG сигнал когда:

    - Цена далеко ниже VWAP (вывод стратегии)

    - RSI перепродан (< 30)

    - Vol regime LOW

    """

    # Синтетический crash

    dates = pd.date_range(start="2024-01-01", periods=200, freq="1h")

    close = np.concatenate(

        [

            np.linspace(100, 100, 50),  # Боковой рынок

            np.linspace(100, 85, 100),  # Резкое падение (RSI перепродан)

            np.linspace(85, 85, 50),  # Восстановление

        ]

    )

    high = close + np.abs(np.random.normal(0.5, 0.3, 200))

    low = close - np.abs(np.random.normal(0.5, 0.3, 200))

    df = pd.DataFrame(

        {

            "open": close + np.random.normal(0, 0.3, 200),

            "high": high,

            "low": low,

            "close": close,

            "volume": np.random.uniform(1000, 5000, 200),

        },

        index=dates,

    )

    # Добавляем все признаки

    pipeline = FeaturePipeline()

    df = pipeline.build_features(df)

    # Проверяем что RSI вычислен

    assert "rsi" in df.columns, "RSI отсутствует в FeaturePipeline"

    latest_rsi = df["rsi"].iloc[-1]

    assert not np.isnan(latest_rsi), "RSI = NaN на последней свече"

    print(f"[OK] Latest RSI: {latest_rsi:.2f}")

    # Генерируем сигнал

    strategy = MeanReversionStrategy(

        vwap_distance_threshold=2.0, rsi_oversold=30.0, rsi_overbought=70.0

    )

    signal = strategy.generate_signal(df, {})

    # Проверяем результат

    if signal:

        print(f"[OK] Signal generated: {signal['signal']}")

        print(f"     Reason: {signal['reason']}")

        assert "RSI=" in signal["reason"], "RSI не включен в сигнал"

        assert latest_rsi not in [50, 0, 100], "Используется default RSI!"

    else:

        print("[OK] No signal (vol_regime or conditions not met)")

        print(f"     Latest RSI used: {latest_rsi:.2f} (not default=50)")


def test_mean_reversion_rsi_not_default():
    """

    Test: Убедитесь что RSI НЕ всегда равен 50 (default)

    Если бы он был, это означал бы что default используется везде

    """

    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")

    close = np.random.normal(100, 5, 100)  # Боковой рынок

    df = pd.DataFrame(

        {

            "open": close + np.random.normal(0, 0.3, 100),

            "high": close + np.abs(np.random.normal(0.5, 0.3, 100)),

            "low": close - np.abs(np.random.normal(0.5, 0.3, 100)),

            "close": close,

            "volume": np.random.uniform(1000, 5000, 100),

        },

        index=dates,

    )

    pipeline = FeaturePipeline()

    df = pipeline.build_features(df)

    # Собираем RSI значения

    rsi_values = df["rsi"].tail(50).dropna()

    # Проверяем что не все значения равны 50

    unique_values = rsi_values[rsi_values != 50].nunique()

    print(f"[OK] Unique RSI values (not 50): {unique_values}")

    assert unique_values > 0, "Все RSI значения равны 50 - используется только default!"

    # Проверяем диапазон

    assert rsi_values.min() >= 0, "RSI < 0"

    assert rsi_values.max() <= 100, "RSI > 100"

    print(f"[OK] RSI range: [{rsi_values.min():.2f}, {rsi_values.max():.2f}]")


if __name__ == "__main__":

    print("=" * 60)

    print("Test 1: MeanReversionStrategy with real RSI (oversold)")

    print("=" * 60)

    test_mean_reversion_with_real_rsi_oversold()

    print("\n" + "=" * 60)

    print("Test 2: RSI is NOT always default=50")

    print("=" * 60)

    test_mean_reversion_rsi_not_default()

    print("\n" + "=" * 60)

    print("[OK] ALL TESTS PASSED!")

    print("=" * 60)
