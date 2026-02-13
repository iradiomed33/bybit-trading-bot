"""
Интеграционные тесты для Weighted Strategy Routing

Сценарии:
1. Trend regime → выбирается TrendPullback (высокий вес)
2. Range regime → выбирается MeanReversion (высокий вес)
3. High spread/ATR → все кандидаты отклоняются hygiene filters
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock

from strategy.meta_layer import MetaLayer
from strategy.regime_scorer import RegimeScorer


class MockStrategy:
    """Mock стратегия для тестов"""
    
    def __init__(self, name: str, signal_pattern: dict = None):
        self.name = name
        self.is_enabled = True
        self._signal_pattern = signal_pattern or {}
    
    def generate_signal(self, df, features):
        """Возвращает заданный паттерн сигнала"""
        if not self._signal_pattern:
            return None
        return dict(self._signal_pattern)
    
    def enable(self):
        self.is_enabled = True
    
    def disable(self):
        self.is_enabled = False


class TestWeightedStrategyRouting:
    """Интеграционные тесты weighted routing"""
    
    @pytest.fixture
    def trend_df(self):
        """DataFrame с трендовым режимом"""
        return pd.DataFrame({
            "timestamp": [1700000000],
            "close": [42000.0],
            "open": [41500.0],
            "high": [42100.0],
            "low": [41400.0],
            "volume": [1000.0],
            # Trend indicators
            "adx": [35.0],           # Сильный тренд
            "ADX_14": [35.0],
            "ema_20": [41800.0],     # EMA20 > EMA50
            "ema_50": [41000.0],
            "bb_width": [0.05],
            "bb_width_pct_change": [0.15],  # Расширение
            "atr_percent": [2.5],
            "atr": [1000.0],
            "atr_slope": [0.3],
            "volume_zscore": [0.5],
            "spread_percent": [0.1],
            "depth_imbalance": [0.1],
        })
    
    @pytest.fixture
    def range_df(self):
        """DataFrame с range режимом"""
        return pd.DataFrame({
            "timestamp": [1700000000],
            "close": [42000.0],
            "open": [41950.0],
            "high": [42050.0],
            "low": [41950.0],
            "volume": [500.0],
            # Range indicators (усиленные для чёткого определения)
            "adx": [10.0],           # Очень низкий ADX
            "ADX_14": [10.0],
            "ema_20": [41995.0],
            "ema_50": [42000.0],     # Почти идентичные EMA
            "bb_width": [0.015],     # Очень узкие BB
            "bb_width_pct_change": [-0.10],  # Активное сужение
            "atr_percent": [1.5],
            "atr": [600.0],
            "atr_slope": [0.05],     # Очень стабильный ATR
            "volume_zscore": [0.0],
            "spread_percent": [0.1],
            "depth_imbalance": [0.0],
        })
    
    @pytest.fixture
    def high_spread_df(self):
        """DataFrame с высоким spread (hygiene filter trigger)"""
        return pd.DataFrame({
            "timestamp": [1700000000],
            "close": [42000.0],
            "open": [41900.0],
            "high": [42100.0],
            "low": [41800.0],
            "volume": [1000.0],
            "adx": [25.0],
            "ADX_14": [25.0],
            "ema_20": [41800.0],
            "ema_50": [41500.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.05],
            "atr_percent": [20.0],   # Очень высокий ATR% → hygiene filter
            "atr": [8000.0],
            "atr_slope": [0.5],
            "volume_zscore": [1.0],
            "spread_percent": [1.5],  # Высокий spread → hygiene filter
            "depth_imbalance": [0.2],
        })
    
    def test_trend_regime_selects_pullback(self, trend_df):
        """
        Тест: в trend режиме TrendPullback получает высокий вес и выбирается
        """
        # Создаём mock стратегии
        pullback = MockStrategy("TrendPullback", {
            "signal": "long",
            "confidence": 0.70,
            "reasons": ["ema_pullback"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41000.0,
        })
        
        mean_reversion = MockStrategy("MeanReversion", {
            "signal": "long",
            "confidence": 0.75,  # Даже выше confidence
            "reasons": ["oversold_rsi"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41500.0,
        })
        
        # Создаём MetaLayer с weighted routing
        meta_layer = MetaLayer(
            strategies=[pullback, mean_reversion],
            use_mtf=False,  # Отключаем MTF для упрощения
            use_weighted_routing=True,
        )
        
        features = {
            "symbol": "BTCUSDT",
            "spread_percent": 0.1,
            "depth_imbalance": 0.1,
        }
        
        # Получаем сигнал
        signal = meta_layer.get_signal(trend_df, features)
        
        # Проверки
        assert signal is not None, "Должен быть выбран сигнал"
        assert signal["strategy"] == "TrendPullback", "В trend должен выбираться TrendPullback"
        assert signal["regime"] == "trend_up"
        assert "final_score" in signal
        assert "regime_scores" in signal
    
    def test_range_regime_selects_mean_reversion(self, range_df):
        """
        Тест: в range режиме MeanReversion получает высокий вес и выбиraется
        """
        pullback = MockStrategy("TrendPullback", {
            "signal": "long",
            "confidence": 0.80,  # Высокая уверенность
            "reasons": ["ema_pullback"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41000.0,
        })
        
        mean_reversion = MockStrategy("MeanReversion", {
            "signal": "long",
            "confidence": 0.65,  # Ниже confidence
            "reasons": ["oversold_rsi"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41500.0,
        })
        
        meta_layer = MetaLayer(
            strategies=[pullback, mean_reversion],
            use_mtf=False,
            use_weighted_routing=True,
        )
        
        features = {
            "symbol": "BTCUSDT",
            "spread_percent": 0.1,
        }
        
        signal = meta_layer.get_signal(range_df, features)
        
        # В range MeanReversion имеет вес 1.5, TrendPullback - 0.5
        # MeanReversion: 0.65 * 1.5 = 0.975
        # TrendPullback: 0.80 * 0.5 = 0.40
        assert signal is not None
        assert signal["strategy"] == "MeanReversion", "В range должен выбираться MeanReversion"
        assert signal["regime"] == "range"
    
    def test_hygiene_filters_block_all(self, high_spread_df):
        """
        Тест: hygiene filters блокируют все кандидаты при плохих условиях
        """
        pullback = MockStrategy("TrendPullback", {
            "signal": "long",
            "confidence": 0.90,
            "reasons": ["perfect_setup"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41000.0,
        })
        
        meta_layer = MetaLayer(
            strategies=[pullback],
            use_mtf=False,
            use_weighted_routing=True,
            no_trade_zone_max_spread_pct=0.50,  # Лимит 0.5%
            no_trade_zone_max_atr_pct=14.0,      # Лимит 14%
        )
        
        features = {
            "symbol": "BTCUSDT",
            "spread_percent": 1.5,   # Превышает лимит
        }
        
        signal = meta_layer.get_signal(high_spread_df, features)
        
        # Все кандидаты должны быть отклонены
        assert signal is None, "При плохих условиях сигнал должен быть None"
    
    def test_confidence_scaling(self):
        """
        Тест: confidence scaling применяется корректно
        """
        strategy = MockStrategy("TrendPullback", {
            "signal": "long",
            "confidence": 0.80,
            "reasons": ["test"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41000.0,
        })
        
        # Конфиг со scaling
        confidence_scaling = {
            "enabled": True,
            "TrendPullback": {
                "multiplier": 0.9,
                "offset": 0.05,
            }
        }
        
        meta_layer = MetaLayer(
            strategies=[strategy],
            use_mtf=False,
            use_weighted_routing=True,
            confidence_scaling_config=confidence_scaling,
        )
        
        trend_df = pd.DataFrame({
            "timestamp": [1700000000],
            "close": [42000.0],
            "adx": [30.0],
            "ADX_14": [30.0],
            "ema_20": [41800.0],
            "ema_50": [41000.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.10],
            "atr_percent": [2.0],
            "atr": [800.0],
            "atr_slope": [0.2],
            "volume_zscore": [0.5],
        })
        
        features = {"symbol": "BTCUSDT"}
        signal = meta_layer.get_signal(trend_df, features)
        
        # Scaled confidence = 0.9 * 0.80 + 0.05 = 0.77
        assert signal is not None
        assert signal["scaled_confidence"] == pytest.approx(0.77, abs=0.01)
    
    def test_regime_scorer_integration(self):
        """
        Тест: RegimeScorer корректно интегрирован в MetaLayer
        """
        strategy = MockStrategy("TrendPullback", {
            "signal": "long",
            "confidence": 0.75,
            "reasons": ["test"],
            "values": {},
            "entry_price": 42000.0,
            "stop_loss": 41000.0,
        })
        
        # Кастомные параметры для RegimeScorer
        regime_scorer_config = {
            "adx_trend_min": 20.0,
            "adx_trend_max": 45.0,
        }
        
        meta_layer = MetaLayer(
            strategies=[strategy],
            use_mtf=False,
            use_weighted_routing=True,
            regime_scorer_config=regime_scorer_config,
        )
        
        trend_df = pd.DataFrame({
            "timestamp": [1700000000],
            "close": [42000.0],
            "adx": [35.0],
            "ADX_14": [35.0],
            "ema_20": [41800.0],
            "ema_50": [41000.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.10],
            "atr_percent": [2.0],
            "atr": [800.0],
            "atr_slope": [0.2],
            "volume_zscore": [0.5],
        })
        
        features = {"symbol": "BTCUSDT"}
        signal = meta_layer.get_signal(trend_df, features)
        
        assert signal is not None
        assert "regime_scores" in signal
        assert signal["regime_scores"]["regime_label"] == "trend_up"
        assert signal["regime_scores"]["trend_score"] > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
