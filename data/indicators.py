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

    _USE_PANDAS_TA = True

except ImportError:

    logger.warning("pandas_ta not available, using manual indicator calculation")

    _USE_PANDAS_TA = False

# Backward-compatible alias for old constant name.
USE_PANDAS_TA = _USE_PANDAS_TA


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
        """ADX (Average Directional Index) - сила тренда. Каноническое имя: adx"""

        if USE_PANDAS_TA:

            adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)

            df = pd.concat([df, adx_df], axis=1)

            # Нормализовать имена из pandas_ta (может быть ADX_14, DI+_14, DI-_14)

            if f"ADX_{period}" in df.columns and "adx" not in df.columns:

                df["adx"] = df[f"ADX_{period}"]

                df = df.drop(columns=[f"ADX_{period}"])

            if f"DI+_{period}" in df.columns and "dmp" not in df.columns:

                df["dmp"] = df[f"DI+_{period}"]

                df = df.drop(columns=[f"DI+_{period}"])

            if f"DI-_{period}" in df.columns and "dmn" not in df.columns:

                df["dmn"] = df[f"DI-_{period}"]

                df = df.drop(columns=[f"DI-_{period}"])

        else:

            high = df["high"].values

            low = df["low"].values

            close = df["close"].values

            tr1 = high - low

            tr2 = np.abs(high - np.roll(close, 1))

            tr3 = np.abs(low - np.roll(close, 1))

            tr = np.maximum(tr1, np.maximum(tr2, tr3))

            atr = pd.Series(tr, index=df.index).rolling(window=period).mean()

            plus_dm = np.zeros(len(df))

            minus_dm = np.zeros(len(df))

            for i in range(1, len(df)):

                up = high[i] - high[i - 1]

                down = low[i - 1] - low[i]

                if up > down and up > 0:

                    plus_dm[i] = up

                if down > up and down > 0:

                    minus_dm[i] = down

            plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=period).mean() / atr)

            minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=period).mean() / atr)

            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)

            adx = dx.rolling(window=period).mean()

            df["adx"] = adx

            df["dmp"] = plus_di

            df["dmn"] = minus_di

        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ATR (Average True Range) - волатильность"""
        
        # Clean OHLC data from extreme outliers BEFORE calculation
        # Prevents corrupted historical data (e.g. BTC=1.6M) from inflating ATR
        high_clean = df["high"].clip(upper=df["high"].quantile(0.95))
        low_clean = df["low"].clip(lower=df["low"].quantile(0.05))
        close_clean = df["close"].clip(upper=df["close"].quantile(0.95))

        if USE_PANDAS_TA:

            df["atr"] = ta.atr(high_clean, low_clean, close_clean, length=period)

        else:

            high = high_clean.values
            low = low_clean.values
            close = close_clean.values

            # True Range calculation using pandas shift for correct handling
            prev_close = close_clean.shift(1).values
            
            tr1 = high - low
            tr2 = np.abs(high - prev_close)
            tr3 = np.abs(low - prev_close)

            # Use fmax to ignore NaN in first element
            tr = np.fmax(tr1, np.fmax(tr2, tr3))

            df["atr"] = pd.Series(tr, index=df.index).rolling(window=period).mean()

        # Use cleaned close for percentage calculation
        df["atr_percent"] = (df["atr"] / close_clean) * 100
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        if len(df) > 0:
            last_close = df["close"].iloc[-1]
            last_high = df["high"].iloc[-1]
            last_low = df["low"].iloc[-1]
            last_atr = df["atr"].iloc[-1]
            last_atr_pct = df["atr_percent"].iloc[-1]
            # Log price range to detect anomalies
            high_min = df["high"].min()
            high_max = df["high"].max()
            close_min = df["close"].min()
            close_max = df["close"].max()
            logger.info(f"ATR_CALC: close={last_close:.2f} (H={last_high:.2f}, L={last_low:.2f}), atr={last_atr:.2f}, atr%={last_atr_pct:.2f}% | PriceRange: close({close_min:.2f}-{close_max:.2f}), high({high_min:.2f}-{high_max:.2f})")

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

        if f"BBL_{period}_{std}" in df.columns and f"BBU_{period}_{std}" in df.columns:

            df["bb_width"] = (df[f"BBU_{period}_{std}"] - df[f"BBL_{period}_{std}"]) / df[

                f"BBM_{period}_{std}"

            ]

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

            vwap = (typical_price * df["volume"]).rolling(window=20).sum() / df["volume"].rolling(

                window=20

            ).sum()

            df["vwap"] = vwap

        df["vwap_distance"] = ((df["close"] - df["vwap"]) / df["vwap"]) * 100

        return df

    @staticmethod
    def calculate_volume_features(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Признаки объёма"""

        if USE_PANDAS_TA:

            df["volume_sma"] = ta.sma(df["volume"], length=period)

        else:

            df["volume_sma"] = df["volume"].rolling(window=period).mean()

        volume_std = df["volume"].rolling(period).std()

        df["volume_zscore"] = (df["volume"] - df["volume_sma"]) / (volume_std + 1e-6)

        price_change = df["close"].pct_change()

        df["volume_impulse"] = df["volume_zscore"] * abs(price_change)

        return df

    @staticmethod
    def detect_market_structure(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
        """Детектор структуры рынка"""

        df["swing_high"] = (

            (df["high"] > df["high"].shift(1))

            & (df["high"] > df["high"].shift(-1))

            & (df["high"] == df["high"].rolling(lookback).max())

        )

        df["swing_low"] = (

            (df["low"] < df["low"].shift(1))

            & (df["low"] < df["low"].shift(-1))

            & (df["low"] == df["low"].rolling(lookback).min())

        )

        hh = df["high"].rolling(lookback).max()

        ll = df["low"].rolling(lookback).min()

        structure = pd.Series(0, index=df.index)

        structure[hh == hh.shift(1)] = 0

        structure[hh > hh.shift(1)] = 1

        structure[ll < ll.shift(1)] = -1

        df["structure"] = structure

        return df

    @staticmethod
    def calculate_ema_distance(df: pd.DataFrame, ema_period: int = 20) -> pd.DataFrame:
        """
        Расчёт расстояния от цены до EMA в единицах ATR.
        
        Используется для EMA-router: pullback когда близко, breakout когда далеко.
        
        Args:
            df: DataFrame с данными
            ema_period: Период EMA для расчёта расстояния (по умолчанию 20)
            
        Returns:
            DataFrame с добавленной колонкой ema_distance_atr
        """
        ema_col = f"ema_{ema_period}"
        
        if ema_col not in df.columns or "atr" not in df.columns or "close" not in df.columns:
            df["ema_distance_atr"] = float("nan")
            return df
        
        # Расстояние = |close - EMA| / ATR
        df["ema_distance_atr"] = (df["close"] - df[ema_col]).abs() / df["atr"]
        
        # Обработка случаев с нулевым ATR
        df.loc[df["atr"] == 0, "ema_distance_atr"] = float("nan")
        
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
            
            # EMA-router metric: расстояние до EMA в единицах ATR
            df = TechnicalIndicators.calculate_ema_distance(df)

            return df

        except Exception as e:

            logger.error(f"Error calculating indicators: {e}")

            raise
