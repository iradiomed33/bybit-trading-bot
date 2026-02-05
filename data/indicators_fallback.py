"""
Fallback indicators when pandas-ta is not available.
Простая реализация технических индикаторов в pure NumPy/Pandas.
"""

import numpy as np
import pandas as pd
from logger import setup_logger

logger = setup_logger(__name__)


class TechnicalIndicators:
    """Расчёт технических индикаторов без pandas-ta"""

    @staticmethod
    def calculate_ema(
        df: pd.DataFrame, column: str = "close", periods: list = None
    ) -> pd.DataFrame:
        """Экспоненциальные скользящие средние (EMA)"""
        if periods is None:
            periods = [10, 20, 50, 200]

        for period in periods:
            df[f"ema_{period}"] = df[column].ewm(span=period, adjust=False).mean()

        return df

    @staticmethod
    def calculate_sma(
        df: pd.DataFrame, column: str = "close", periods: list = None
    ) -> pd.DataFrame:
        """Простые скользящие средние (SMA)"""
        if periods is None:
            periods = [10, 20, 50, 200]

        for period in periods:
            df[f"sma_{period}"] = df[column].rolling(window=period).mean()

        return df

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ADX (Average Directional Index) - сила тренда"""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # True Range
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = pd.Series(tr).rolling(window=period).mean()

        # Directional Indicators
        plus_dm = np.zeros(len(df))
        minus_dm = np.zeros(len(df))

        for i in range(1, len(df)):
            up = high[i] - high[i - 1]
            down = low[i - 1] - low[i]

            if up > down and up > 0:
                plus_dm[i] = up
            else:
                plus_dm[i] = 0

            if down > up and down > 0:
                minus_dm[i] = down
            else:
                minus_dm[i] = 0

        plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)

        # ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = pd.Series(dx).rolling(window=period).mean()

        df["adx"] = adx
        df["dmp"] = plus_di
        df["dmn"] = minus_di

        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ATR (Average True Range) - волатильность"""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # True Range
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        df["atr"] = pd.Series(tr).rolling(window=period).mean()
        df["atr_percent"] = (df["atr"] / df["close"]) * 100

        return df

    @staticmethod
    def calculate_bollinger_bands(
        df: pd.DataFrame, period: int = 20, std: float = 2.0
    ) -> pd.DataFrame:
        """Bollinger Bands - полосы Боллинджера"""
        sma = df["close"].rolling(window=period).mean()
        std_dev = df["close"].rolling(window=period).std()

        df[f"BBU_{period}_{std}"] = sma + (std_dev * std)
        df[f"BBM_{period}_{std}"] = sma
        df[f"BBL_{period}_{std}"] = sma - (std_dev * std)

        # Ширина полос
        df["bb_width"] = (df[f"BBU_{period}_{std}"] - df[f"BBL_{period}_{std}"]) / df[
            f"BBM_{period}_{std}"
        ]

        # Позиция цены относительно полос
        df["bb_percent"] = (df["close"] - df[f"BBL_{period}_{std}"]) / (
            df[f"BBU_{period}_{std}"] - df[f"BBL_{period}_{std}"]
        )

        return df

    @staticmethod
    def calculate_macd(
        df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """MACD (Moving Average Convergence Divergence)"""
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """RSI (Relative Strength Index)"""
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    @staticmethod
    def calculate_stochastic(
        df: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3
    ) -> pd.DataFrame:
        """Stochastic Oscillator"""
        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()

        k = 100 * ((df["close"] - low_min) / (high_max - low_min))
        df["%K"] = k.rolling(window=smooth_k).mean()
        df["%D"] = df["%K"].rolling(window=smooth_d).mean()

        return df

    @staticmethod
    def calculate_volume_indicators(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Объемные индикаторы"""
        df["volume_sma"] = df["volume"].rolling(window=period).mean()
        df["volume_zscore"] = (
            df["volume"] - df["volume_sma"]
        ) / df["volume"].rolling(window=period).std()

        return df

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Расчёт всех индикаторов"""
        try:
            df = TechnicalIndicators.calculate_ema(df)
            df = TechnicalIndicators.calculate_sma(df)
            df = TechnicalIndicators.calculate_adx(df)
            df = TechnicalIndicators.calculate_atr(df)
            df = TechnicalIndicators.calculate_bollinger_bands(df)
            df = TechnicalIndicators.calculate_macd(df)
            df = TechnicalIndicators.calculate_rsi(df)
            df = TechnicalIndicators.calculate_stochastic(df)
            df = TechnicalIndicators.calculate_volume_indicators(df)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            raise
