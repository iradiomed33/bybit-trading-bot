"""
Технические индикаторы для feature pipeline.
Со встроенной поддержкой fallback реализации без pandas_ta.
"""

import numpy as np
import pandas as pd
from logger import setup_logger

logger = setup_logger(__name__)

# Try to import pandas_ta, fallback to manual implementation
try:
    import pandas_ta as ta
    USE_PANDAS_TA = True
except ImportError:
    logger.warning("pandas_ta not available, using manual indicator calculation")
    USE_PANDAS_TA = False


class TechnicalIndicators:
    """Расчёт технических индикаторов с fallback support"""

    @staticmethod
    def calculate_ema(
        df: pd.DataFrame, column: str = "close", periods: list = None
    ) -> pd.DataFrame:
        """Экспоненциальные скользящие средние (EMA)"""
        if periods is None:
            periods = [10, 20, 50, 200]

        for period in periods:
            if USE_PANDAS_TA:
                df[f"ema_{period}"] = ta.ema(df[column], length=period)
            else:
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
            if USE_PANDAS_TA:
                df[f"sma_{period}"] = ta.sma(df[column], length=period)
            else:
                df[f"sma_{period}"] = df[column].rolling(window=period).mean()

        return df

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ADX (Average Directional Index) - сила тренда"""
        if USE_PANDAS_TA:
            adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
            df = pd.concat([df, adx_df], axis=1)
        else:
            # Fallback реализация
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
                if down > up and down > 0:
                    minus_dm[i] = down

            plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
            minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)

            # ADX
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
            adx = pd.Series(dx).rolling(window=period).mean()

            df["adx"] = adx.values
            df["dmp"] = plus_di.values
            df["dmn"] = minus_di.values

        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ATR (Average True Range) - волатильность"""
        if USE_PANDAS_TA:
            df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=period)
        else:
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values

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
        if USE_PANDAS_TA:
            bb = ta.bbands(df["close"], length=period, std=std)
            df = pd.concat([df, bb], axis=1)
        else:
            sma = df["close"].rolling(window=period).mean()
            std_dev = df["close"].rolling(window=period).std()

            df[f"BBU_{period}_{std}"] = sma + (std_dev * std)
            df[f"BBM_{period}_{std}"] = sma
            df[f"BBL_{period}_{std}"] = sma - (std_dev * std)

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
        if USE_PANDAS_TA:
            df["rsi"] = ta.rsi(df["close"], length=period)
        else:
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df["rsi"] = 100 - (100 / (1 + rs))

        return df

    @staticmethod
    def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
        """OBV (On-Balance Volume) - накопление объёма"""
        if USE_PANDAS_TA:
            df["obv"] = ta.obv(df["close"], df["volume"])
        else:
            obv = pd.Series(0.0, index=df.index)
            for i in range(1, len(df)):
                if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                    obv.iloc[i] = obv.iloc[i - 1] + df["volume"].iloc[i]
                elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
                    obv.iloc[i] = obv.iloc[i - 1] - df["volume"].iloc[i]
                else:
                    obv.iloc[i] = obv.iloc[i - 1]
            df["obv"] = obv

        return df

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
        """VWAP (Volume Weighted Average Price)"""
        if USE_PANDAS_TA:
            df["vwap"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        else:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            vwap = (typical_price * df["volume"]).rolling(window=20).sum() / df["volume"].rolling(window=20).sum()
            df["vwap"] = vwap

        df["vwap_distance"] = ((df["close"] - df["vwap"]) / df["vwap"]) * 100
        return df

    @staticmethod
    def calculate_volume_features(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Признаки объёма"""
        # Средний объём
        if USE_PANDAS_TA:
            df["volume_sma"] = ta.sma(df["volume"], length=period)
        else:
            df["volume_sma"] = df["volume"].rolling(window=period).mean()

        # Z-score объёма
        volume_std = df["volume"].rolling(period).std()
        df["volume_zscore"] = (df["volume"] - df["volume_sma"]) / (volume_std + 1e-6)

        # Импульс объёма
        price_change = df["close"].pct_change()
        df["volume_impulse"] = df["volume_zscore"] * abs(price_change)

        return df

    @staticmethod
    def detect_market_structure(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
        """Детектор структуры рынка"""
        # Swing highs
        df["swing_high"] = (
            (df["high"] > df["high"].shift(1))
            & (df["high"] > df["high"].shift(-1))
            & (df["high"] == df["high"].rolling(lookback).max())
        )

        # Swing lows
        df["swing_low"] = (
            (df["low"] < df["low"].shift(1))
            & (df["low"] < df["low"].shift(-1))
            & (df["low"] == df["low"].rolling(lookback).min())
        )

        # Структура: 1=вверх, -1=вниз, 0=флэт
        hh = df["high"].rolling(lookback).max()
        ll = df["low"].rolling(lookback).min()

        structure = pd.Series(0, index=df.index)
        structure[hh == hh.shift(1)] = 0
        structure[hh > hh.shift(1)] = 1
        structure[ll < ll.shift(1)] = -1

        df["structure"] = structure

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
            df = TechnicalIndicators.calculate_rsi(df)
            df = TechnicalIndicators.calculate_obv(df)
            df = TechnicalIndicators.calculate_vwap(df)
            df = TechnicalIndicators.calculate_volume_features(df)
            df = TechnicalIndicators.detect_market_structure(df)

            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            raise
