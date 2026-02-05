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

        # Если тень > 3x тела - аномалия
        df["anomaly_wick"] = ((upper_wick > 3 * body) | (lower_wick > 3 * body)).astype(int)

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
            "close", "adx", "rsi", "atr", "atr_percent",
            "ema_10", "ema_20", "ema_50", "ema_200",
            "sma_20", "sma_50",
            "volume_zscore", "realized_vol"
        ]
        df = ensure_required_columns(df, required_columns)

        logger.info(f"Features built: {len(df.columns)} columns, {len(df)} rows")

        return df
