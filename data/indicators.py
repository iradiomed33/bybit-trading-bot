"""
Технические индикаторы для feature pipeline.
Используем pandas-ta для расчёта индикаторов.
"""

# import numpy as np
import pandas as pd
import pandas_ta as ta

# from typing import Optional
from logger import setup_logger

logger = setup_logger(__name__)


class TechnicalIndicators:
    """Расчёт технических индикаторов"""

    @staticmethod
    def calculate_ema(
        df: pd.DataFrame, column: str = "close", periods: list = None
    ) -> pd.DataFrame:
        """
        Экспоненциальные скользящие средние (EMA).

        Args:
            df: DataFrame с OHLCV данными
            column: Колонка для расчёта
            periods: Периоды EMA (например [10, 20, 50, 200])

        Returns:
            DataFrame с добавленными EMA колонками
        """
        if periods is None:
            periods = [10, 20, 50, 200]

        for period in periods:
            df[f"ema_{period}"] = ta.ema(df[column], length=period)

        return df

    @staticmethod
    def calculate_sma(
        df: pd.DataFrame, column: str = "close", periods: list = None
    ) -> pd.DataFrame:
        """Простые скользящие средние (SMA)"""
        if periods is None:
            periods = [10, 20, 50, 200]

        for period in periods:
            df[f"sma_{period}"] = ta.sma(df[column], length=period)

        return df

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ADX (Average Directional Index) - сила тренда.

        Returns:
            Добавляет колонки: adx, dmp (DI+), dmn (DI-)
        """
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
        df = pd.concat([df, adx_df], axis=1)
        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ATR (Average True Range) - волатильность.

        Returns:
            Добавляет колонки: atr, atr_percent (% от цены)
        """
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=period)
        df["atr_percent"] = (df["atr"] / df["close"]) * 100
        return df

    @staticmethod
    def calculate_bollinger_bands(
        df: pd.DataFrame, period: int = 20, std: float = 2.0
    ) -> pd.DataFrame:
        """
        Bollinger Bands - полосы Боллинджера.

        Returns:
            Добавляет: bb_upper, bb_mid, bb_lower, bb_width, bb_percent
        """
        bb = ta.bbands(df["close"], length=period, std=std)
        df = pd.concat([df, bb], axis=1)

        # Ширина полос (нормализованная)
        if f"BBL_{period}_{std}" in df.columns and f"BBU_{period}_{std}" in df.columns:
            df["bb_width"] = (df[f"BBU_{period}_{std}"] - df[f"BBL_{period}_{std}"]) / df[
                f"BBM_{period}_{std}"
            ]

            # Позиция цены относительно полос (0 = нижняя, 1 = верхняя)
            df["bb_percent"] = (df["close"] - df[f"BBL_{period}_{std}"]) / (
                df[f"BBU_{period}_{std}"] - df[f"BBL_{period}_{std}"]
            )

        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """RSI (Relative Strength Index)"""
        df["rsi"] = ta.rsi(df["close"], length=period)
        return df

    @staticmethod
    def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
        """OBV (On-Balance Volume) - накопление объёма"""
        df["obv"] = ta.obv(df["close"], df["volume"])
        return df

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
        """
        VWAP (Volume Weighted Average Price).

        Returns:
            Добавляет: vwap, vwap_distance (% отклонение от VWAP)
        """
        df["vwap"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        df["vwap_distance"] = ((df["close"] - df["vwap"]) / df["vwap"]) * 100
        return df

    @staticmethod
    def calculate_volume_features(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Признаки объёма.

        Returns:
            Добавляет: volume_sma, volume_zscore, volume_impulse
        """
        # Средний объём
        df["volume_sma"] = ta.sma(df["volume"], length=period)

        # Z-score объёма (стандартные отклонения от среднего)
        volume_std = df["volume"].rolling(period).std()
        df["volume_zscore"] = (df["volume"] - df["volume_sma"]) / volume_std

        # Импульс объёма (большой объём + движение цены)
        price_change = df["close"].pct_change()
        df["volume_impulse"] = df["volume_zscore"] * abs(price_change)

        return df

    @staticmethod
    def detect_market_structure(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
        """
        Детектор структуры рынка: Higher Highs (HH), Lower Lows (LL).

        Returns:
            Добавляет: swing_high, swing_low, structure (1=uptrend, -1=downtrend, 0=range)
        """
        # Swing highs: локальные максимумы
        df["swing_high"] = (
            (df["high"] > df["high"].shift(1))
            & (df["high"] > df["high"].shift(-1))
            & (df["high"] == df["high"].rolling(lookback).max())
        )

        # Swing lows: локальные минимумы
        df["swing_low"] = (
            (df["low"] < df["low"].shift(1))
            & (df["low"] < df["low"].shift(-1))
            & (df["low"] == df["low"].rolling(lookback).min())
        )

        # Упрощённое определение структуры
        # 1 = восходящий тренд (HH/HL), -1 = нисходящий (LH/LL), 0 = флэт
        df["structure"] = 0
        df.loc[df["swing_high"] & (df["high"] > df["high"].shift(lookback)), "structure"] = 1
        df.loc[df["swing_low"] & (df["low"] < df["low"].shift(lookback)), "structure"] = -1

        return df
