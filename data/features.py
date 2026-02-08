"""

Feature pipeline: агрегация всех признаков для стратегий.


Блоки:

1. Trend & Structure

2. Volatility

3. Volume

4. Order Flow

5. Derivatives

6. Multi-timeframe

7. Data Quality

"""


import pandas as pd

import numpy as np

from typing import Dict, Any, Optional

from data.indicators import TechnicalIndicators

from data.column_normalizer import normalize_column_names, ensure_required_columns

from logger import setup_logger


logger = setup_logger(__name__)


class FeaturePipeline:

    """

    Центральный класс для расчёта всех признаков.

    """

    def __init__(self):

        self.indicators = TechnicalIndicators()

        logger.info("FeaturePipeline initialized")

    def calculate_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """

        Блок 1: Trend & Market Structure


        Признаки:

        - EMA/SMA на разных периодах

        - Slope EMA (направление)

        - ADX (сила тренда)

        - RSI (импульс, перепроданность/перекупленность)

        - Market structure (HH/HL, LH/LL)

        """

        logger.debug("Calculating trend features...")

        # EMA

        df = self.indicators.calculate_ema(df, periods=[10, 20, 50, 200])

        # SMA

        df = self.indicators.calculate_sma(df, periods=[20, 50])

        # Slope EMA (угол наклона)

        df["ema_20_slope"] = df["ema_20"].diff(5) / 5  # Изменение за 5 периодов

        # ADX

        df = self.indicators.calculate_adx(df)

        # RSI (Relative Strength Index) - для импульса и mean reversion

        df = self.indicators.calculate_rsi(df)

        # Market structure

        df = self.indicators.detect_market_structure(df)

        # Тренд: цена относительно EMA

        df["price_above_ema20"] = (df["close"] > df["ema_20"]).astype(int)

        df["price_above_ema50"] = (df["close"] > df["ema_50"]).astype(int)

        return df

    def calculate_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """

        Блок 2: Volatility


        Признаки:

        - ATR (абсолютная и относительная)

        - Реализованная волатильность

        - Bollinger Bands (ширина, позиция цены)

        - Volatility regime (low/normal/high)

        """

        logger.debug("Calculating volatility features...")

        # ATR

        df = self.indicators.calculate_atr(df)

        # Реализованная волатильность (rolling std returns)

        df["returns"] = df["close"].pct_change()

        df["realized_vol"] = df["returns"].rolling(20).std() * np.sqrt(20)  # 20-период

        # Bollinger Bands

        df = self.indicators.calculate_bollinger_bands(df)

        # STR-004: BB width change (для определения сужения)

        if "bb_width" in df.columns:

            df["bb_width_pct_change"] = df["bb_width"].pct_change(5)  # Изменение за 5 баров

        else:

            df["bb_width_pct_change"] = 0.0

        # STR-004: ATR slope (рост волатильности)

        if "atr" in df.columns:

            df["atr_slope"] = df["atr"].diff(5) / 5  # Изменение ATR за 5 периодов

        else:

            df["atr_slope"] = 0.0

        # STR-006: Squeeze detection (BB width percentile)

        if "bb_width" in df.columns:

            df["bb_width_percentile"] = (

                df["bb_width"]

                .rolling(100)

                .apply(

                    lambda x: (x.iloc[-1] <= x.quantile(0.2)).astype(float) if len(x) > 0 else 0.0,

                    raw=False,

                )

            )

        else:

            df["bb_width_percentile"] = 0.0

        # STR-006: ATR percentile для squeeze

        if "atr_percent" in df.columns:

            df["atr_percentile"] = (

                df["atr_percent"]

                .rolling(100)

                .apply(

                    lambda x: (x.iloc[-1] <= x.quantile(0.2)).astype(float) if len(x) > 0 else 0.0,

                    raw=False,

                )

            )

        else:

            df["atr_percentile"] = 0.0

        # STR-006: Expansion detection (рост после сжатия)

        # BB expansion: рост BB width за последние 3 бара

        if "bb_width" in df.columns:

            df["bb_expansion"] = (df["bb_width"].diff(3) > 0).astype(float)

        else:

            df["bb_expansion"] = 0.0

        # ATR expansion: рост ATR за последние 3 бара

        if "atr" in df.columns:

            df["atr_expansion"] = (df["atr"].diff(3) > 0).astype(float)

        else:

            df["atr_expansion"] = 0.0

        # Volatility regime классификация

        atr_mean = df["atr_percent"].rolling(100).mean()

        atr_std = df["atr_percent"].rolling(100).std()

        df["vol_regime"] = 0  # Normal

        df.loc[df["atr_percent"] < (atr_mean - 0.5 * atr_std), "vol_regime"] = -1  # Low

        df.loc[df["atr_percent"] > (atr_mean + 0.5 * atr_std), "vol_regime"] = 1  # High

        return df

    def calculate_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """

        Блок 3: Volume & Participation


        Признаки:

        - Volume z-score

        - OBV (накопление)

        - VWAP и отклонение от него

        - Volume impulse

        """

        logger.debug("Calculating volume features...")

        # Volume features

        df = self.indicators.calculate_volume_features(df)

        # OBV

        df = self.indicators.calculate_obv(df)

        # VWAP

        df = self.indicators.calculate_vwap(df)

        # STR-006: Volume confirmation features

        if "volume" in df.columns:

            # Volume SMA (20 periods)

            df["volume_sma"] = df["volume"].rolling(20).mean()

            # Volume ratio (current / SMA)

            df["volume_ratio"] = df["volume"] / df["volume_sma"].replace(0, 1)

            # Volume percentile (в топ 20% за последние 100 баров)

            df["volume_percentile"] = (

                df["volume"]

                .rolling(100)

                .apply(

                    lambda x: (x.iloc[-1] >= x.quantile(0.8)).astype(float) if len(x) > 0 else 0.0,

                    raw=False,

                )

            )

        else:

            df["volume_sma"] = 0.0

            df["volume_ratio"] = 1.0

            df["volume_percentile"] = 0.0

        return df

    def calculate_orderflow_features(self, orderbook: Dict[str, Any]) -> Dict[str, float]:
        """

        Блок 4: Order Flow / Liquidity (из стакана)


        Признаки:

        - Spread (спред bid-ask)

        - Midprice

        - Depth imbalance (bid vs ask)

        - Liquidity concentration

        """

        features = {}

        bids = orderbook.get("bids", [])

        asks = orderbook.get("asks", [])

        if not bids or not asks:

            logger.warning("Empty orderbook, skipping orderflow features")

            return features

        # Best bid/ask

        best_bid = float(bids[0][0])

        best_ask = float(asks[0][0])

        # Spread

        features["spread"] = best_ask - best_bid

        features["spread_percent"] = (features["spread"] / best_bid) * 100

        # Midprice

        features["midprice"] = (best_bid + best_ask) / 2

        # Depth imbalance (bid vs ask volume)

        bid_volume = sum(float(b[1]) for b in bids[:10])  # Top 10 уровней

        ask_volume = sum(float(a[1]) for a in asks[:10])

        total_volume = bid_volume + ask_volume

        if total_volume > 0:

            features["depth_imbalance"] = (bid_volume - ask_volume) / total_volume

        else:

            features["depth_imbalance"] = 0

        # Liquidity concentration (% объёма в топ 5 уровнях)

        top5_bid = sum(float(b[1]) for b in bids[:5])

        top5_ask = sum(float(a[1]) for a in asks[:5])

        features["liquidity_concentration"] = (

            (top5_bid + top5_ask) / total_volume if total_volume > 0 else 0

        )

        return features

    def calculate_derivatives_features(

        self,

        mark_price: float,

        index_price: float,

        funding_rate: float,

        open_interest: float,

        oi_change: float,

    ) -> Dict[str, float]:
        """

        Блок 5: Derivatives-aware features


        Признаки:

        - Mark vs Index deviation

        - Premium/discount

        - Funding rate bias

        - Open Interest trend

        """

        features = {}

        # Mark vs Index deviation

        if index_price > 0:

            features["mark_index_deviation"] = ((mark_price - index_price) / index_price) * 100

        else:

            features["mark_index_deviation"] = 0

        # Funding rate

        features["funding_rate"] = funding_rate

        features["funding_bias"] = 1 if funding_rate > 0.01 else (-1 if funding_rate < -0.01 else 0)

        # Open Interest

        features["open_interest"] = open_interest

        features["oi_change"] = oi_change

        return features

    def detect_data_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """

        Блок 7: Data Quality & Anomalies


        Детектирует:

        - Аномальные свечи (huge wick, gap)

        - Низкая ликвидность (малый объём)

        - Пропуски данных

        """

        logger.debug("Detecting data anomalies...")

        # Аномальные свечи (огромные тени)

        body = abs(df["close"] - df["open"])

        upper_wick = df["high"] - df[["close", "open"]].max(axis=1)

        lower_wick = df[["close", "open"]].min(axis=1) - df["low"]

        # Защита от нулевого body (doji-свечи):
        # Используем body_safe = max(body, eps), где eps - минимальный порог
        # Также используем процент от цены для более надежной проверки
        candle_range = df["high"] - df["low"]
        
        # Минимальный порог для body: 0.1% от цены закрытия
        # Если body меньше этого порога, используем сам порог
        min_body_threshold = df["close"] * 0.001
        body_safe = body.where(body > min_body_threshold, min_body_threshold)
        
        # Тень считается аномальной если:
        # 1. Тень > 3x безопасного тела И
        # 2. Тень > 2% от цены (чтобы отфильтровать маленькие doji)
        # Это означает, что экстремальная тень должна быть действительно большой относительно цены
        wick_threshold_percent = df["close"] * 0.02  # 2% от цены
        
        wick_anomaly_condition = (
            ((upper_wick > 3 * body_safe) | (lower_wick > 3 * body_safe)) &
            ((upper_wick > wick_threshold_percent) | (lower_wick > wick_threshold_percent))
        )
        
        df["anomaly_wick"] = wick_anomaly_condition.astype(int)

        # Низкий объём (< 20% от среднего)

        volume_mean = df["volume"].rolling(50).mean()

        df["anomaly_low_volume"] = (df["volume"] < 0.2 * volume_mean).astype(int)

        # Гэп (разрыв между свечами > 1% от цены)

        price_gap = abs(df["open"] - df["close"].shift(1))

        df["anomaly_gap"] = ((price_gap / df["close"]) > 0.01).astype(int)

        # Общий флаг аномалии

        df["has_anomaly"] = (

            (df["anomaly_wick"] == 1) | (df["anomaly_low_volume"] == 1) | (df["anomaly_gap"] == 1)

        ).astype(int)

        return df

    def detect_liquidation_wicks(

        self,

        df: pd.DataFrame,

        atr_multiplier: float = 2.5,

        wick_ratio_threshold: float = 0.7,

        volume_percentile: float = 95.0,

    ) -> pd.DataFrame:
        """

        STR-002: Детекция ликвидационных свечей (liquidation wicks)


        Ликвидационная свеча - это свеча с экстремальными параметрами:

        1. Большой диапазон: candle_range > atr_multiplier * ATR

        2. Большие тени: upper/lower_wick_ratio > threshold (тень >> тело)

        3. Всплеск объёма: volume > percentile


        Args:

            df: DataFrame с OHLCV и ATR

            atr_multiplier: Множитель ATR для определения большого диапазона

            wick_ratio_threshold: Порог отношения тени к телу (0.7 = тень 70% от полного диапазона)

            volume_percentile: Перцентиль объёма для определения всплеска


        Returns:

            DataFrame с колонкой 'liquidation_wick' (1 = detected, 0 = normal)

        """

        logger.debug("Detecting liquidation wicks...")

        # 1. Candle range (high - low)

        candle_range = df["high"] - df["low"]

        # 2. Body (abs(close - open))

        body = abs(df["close"] - df["open"])

        # 3. Wicks

        upper_wick = df["high"] - df[["close", "open"]].max(axis=1)

        lower_wick = df[["close", "open"]].min(axis=1) - df["low"]

        max_wick = pd.concat([upper_wick, lower_wick], axis=1).max(axis=1)

        # 4. Wick ratio (максимальная тень / полный диапазон)

        wick_ratio = max_wick / (candle_range + 1e-6)  # Избегаем деления на 0

        # Условие 1: Большой диапазон (> k * ATR)

        if "atr" in df.columns:

            large_range = candle_range > (atr_multiplier * df["atr"])

        else:

            # Фоллбэк: если нет ATR, используем rolling std

            rolling_std = df["close"].rolling(20).std()

            large_range = candle_range > (atr_multiplier * rolling_std)

        # Условие 2: Большие тени (тень занимает > threshold от диапазона)

        large_wick = wick_ratio > wick_ratio_threshold

        # Условие 3: Всплеск объёма (> percentile)

        # Используем минимум между 100 и длиной данных для rolling window

        volume_window = min(100, len(df))

        volume_threshold = (

            df["volume"].rolling(volume_window, min_periods=1).quantile(volume_percentile / 100)

        )

        volume_spike = df["volume"] > volume_threshold

        # Ликвидационная свеча = (большой диапазон ИЛИ большие тени) И всплеск объёма

        df["liquidation_wick"] = (((large_range) | (large_wick)) & (volume_spike)).astype(int)

        # Дополнительные метрики для анализа

        df["candle_range_atr"] = candle_range / (df.get("atr", 1) + 1e-6)

        df["wick_ratio"] = wick_ratio

        # Подсчёт обнаруженных ликвидационных свечей

        liq_count = df["liquidation_wick"].sum()

        if liq_count > 0:

            logger.debug(f"Detected {liq_count} liquidation wicks in {len(df)} candles")

        return df

    def build_features(

        self,

        df: pd.DataFrame,

        orderbook: Optional[Dict[str, Any]] = None,

        derivatives_data: Optional[Dict[str, float]] = None,

    ) -> pd.DataFrame:
        """

        Собрать все признаки.


        Args:

            df: DataFrame с OHLCV данными

            orderbook: Данные стакана (опционально)

            derivatives_data: Деривативные метрики (опционально)


        Returns:

            DataFrame с полным набором признаков

        """

        logger.info("Building features...")

        # 1. Trend

        df = self.calculate_trend_features(df)

        # 2. Volatility

        df = self.calculate_volatility_features(df)

        # 3. Volume

        df = self.calculate_volume_features(df)

        # 7. Data quality

        df = self.detect_data_anomalies(df)

        # 7b. STR-002: Liquidation wicks detection

        df = self.detect_liquidation_wicks(df)

        # 4. Order Flow (если есть стакан)

        if orderbook:

            orderflow_features = self.calculate_orderflow_features(orderbook)

            # Добавляем как последнюю строку (актуальные данные)

            for key, value in orderflow_features.items():

                df.loc[df.index[-1], key] = value

        # 5. Derivatives (если есть данные)

        if derivatives_data:

            deriv_features = self.calculate_derivatives_features(**derivatives_data)

            for key, value in deriv_features.items():

                df.loc[df.index[-1], key] = value

        # Нормализовать имена колонок (ADX_14 → adx и т.д.)

        df = normalize_column_names(df)

        # Гарантировать наличие обязательных колонок

        required_columns = [

            "close",

            "adx",

            "rsi",

            "atr",

            "atr_percent",

            "ema_10",

            "ema_20",

            "ema_50",

            "ema_200",

            "sma_20",

            "sma_50",

            "volume_zscore",

            "realized_vol",

        ]

        df = ensure_required_columns(df, required_columns)

        logger.info(f"Features built: {len(df.columns)} columns, {len(df)} rows")

        return df
