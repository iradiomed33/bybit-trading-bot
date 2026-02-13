"""
Unit-тесты для RegimeScorer

Проверяем:
1. Trend режим (высокий ADX, согласованность EMA)
2. Range режим (низкий ADX, узкие BB)
3. High volatility режим (высокий ATR%)
"""

import pytest
import pandas as pd
import numpy as np
from strategy.regime_scorer import RegimeScorer, RegimeScores


class TestRegimeScorer:
    """Тесты для Market Regime Scorer"""
    
    @pytest.fixture
    def scorer(self):
        """Создать scorer с дефолтными параметрами"""
        return RegimeScorer()
    
    def test_trend_up_scenario(self, scorer):
        """Тест: сильный восходящий тренд"""
        # Данные: высокий ADX, EMA20 > EMA50, цена выше, BB расширяется
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [35.0],           # Сильный ADX
            "ADX_14": [35.0],
            "ema_20": [102.0],       # EMA20 выше EMA50
            "ema_50": [95.0],
            "bb_width": [0.05],
            "bb_width_pct_change": [0.15],  # Расширение
            "atr_percent": [2.0],
            "atr_slope": [0.3],
            "volume_zscore": [0.5],
        })
        
        scores = scorer.score_regime(df)
        
        # Проверки
        assert scores.trend_score > 0.5, "Trend score должен быть высоким"
        assert scores.range_score < 0.5, "Range score должен быть низким"
        assert scores.regime_label == "trend_up"
        assert "strong_adx" in scores.reasons or "ema_aligned_up" in scores.reasons
        assert scores.confidence > 0.5
        
        # Структура данных
        assert 0.0 <= scores.trend_score <= 1.0
        assert 0.0 <= scores.range_score <= 1.0
        assert 0.0 <= scores.volatility_score <= 1.0
        assert 0.0 <= scores.chop_score <= 1.0
    
    def test_trend_down_scenario(self, scorer):
        """Тест: сильный нисходящий тренд"""
        df = pd.DataFrame({
            "close": [88.0],
            "adx": [40.0],
            "ADX_14": [40.0],
            "ema_20": [90.0],        # EMA20 ниже EMA50
            "ema_50": [95.0],
            "bb_width": [0.06],
            "bb_width_pct_change": [0.10],
            "atr_percent": [2.5],
            "atr_slope": [0.2],
            "volume_zscore": [1.0],
        })
        
        scores = scorer.score_regime(df)
        
        assert scores.trend_score > 0.5
        assert scores.regime_label == "trend_down"
        assert "strong_adx" in scores.reasons or "ema_aligned_down" in scores.reasons
    
    def test_range_scenario(self, scorer):
        """Тест: флэт/диапазон"""
        df = pd.DataFrame({
            "close": [97.0],
            "adx": [10.0],           # Очень низкий ADX для чёткого range
            "ADX_14": [10.0],
            "ema_20": [96.5],
            "ema_50": [97.0],        # Очень близкие EMA
            "bb_width": [0.015],     # Очень узкие BB (половина от порога)
            "bb_width_pct_change": [-0.10],  # Активное сужение
            "atr_percent": [1.5],
            "atr_slope": [0.05],     # Очень стабильный ATR
            "volume_zscore": [0.0],
        })
        
        scores = scorer.score_regime(df)
        
        assert scores.range_score > 0.5, f"Range score должен быть высоким, получен {scores.range_score}"
        assert scores.trend_score < 0.5, "Trend score должен быть низким"
        assert scores.regime_label == "range"
        assert "low_adx" in scores.reasons or "narrow_bb" in scores.reasons
    
    def test_high_volatility_scenario(self, scorer):
        """Тест: высокая волатильность (приоритет)"""
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [30.0],
            "ADX_14": [30.0],
            "ema_20": [98.0],
            "ema_50": [95.0],
            "bb_width": [0.08],
            "bb_width_pct_change": [0.2],
            "atr_percent": [8.0],    # Экстремальная волатильность
            "atr_slope": [0.5],
            "volume_zscore": [2.0],
        })
        
        scores = scorer.score_regime(df)
        
        assert scores.volatility_score > 0.7, "Volatility score должен быть очень высоким"
        assert scores.regime_label == "high_vol"
        assert "extreme_volatility" in scores.reasons
    
    def test_empty_dataframe(self, scorer):
        """Тест: пустой DataFrame"""
        df = pd.DataFrame()
        
        scores = scorer.score_regime(df)
        
        assert scores.regime_label == "unknown"
        assert scores.trend_score == 0.0
        assert scores.range_score == 0.0
        assert "empty_dataframe" in scores.reasons
    
    def test_missing_indicators(self, scorer):
        """Тест: отсутствуют критически важные индикаторы"""
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [25.0],
            # Нет EMA!
        })
        
        scores = scorer.score_regime(df)
        
        assert scores.regime_label == "unknown"
        assert "missing_critical_indicators" in scores.reasons
    
    def test_to_dict_serialization(self, scorer):
        """Тест: сериализация в dict"""
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [30.0],
            "ADX_14": [30.0],
            "ema_20": [102.0],
            "ema_50": [95.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.10],
            "atr_percent": [2.0],
            "atr_slope": [0.3],
            "volume_zscore": [0.5],
        })
        
        scores = scorer.score_regime(df)
        result_dict = scores.to_dict()
        
        # Проверка структуры
        assert "trend_score" in result_dict
        assert "range_score" in result_dict
        assert "volatility_score" in result_dict
        assert "chop_score" in result_dict
        assert "regime_label" in result_dict
        assert "confidence" in result_dict
        assert "reasons" in result_dict
        assert "values" in result_dict
        
        # Проверка типов
        assert isinstance(result_dict["trend_score"], float)
        assert isinstance(result_dict["reasons"], list)
        assert isinstance(result_dict["values"], dict)
    
    def test_choppy_market_scenario(self, scorer):
        """Тест: пила/choppy market"""
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [12.0],           # Очень низкий ADX
            "ADX_14": [12.0],
            "ema_20": [99.0],
            "ema_50": [100.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.25],  # Резкое изменение
            "atr_percent": [2.5],
            "atr_slope": [1.5],      # Нестабильный ATR
            "volume_zscore": [2.5],  # Аномальный объём
        })
        
        scores = scorer.score_regime(df)
        
        assert scores.chop_score > 0.6, "Chop score должен быть высоким"
        assert scores.regime_label == "choppy"
        assert "high_noise" in scores.reasons or "no_clear_direction" in scores.reasons
    
    def test_with_orderflow_features(self, scorer):
        """Тест: дополнительные orderflow features"""
        df = pd.DataFrame({
            "close": [100.0],
            "adx": [30.0],
            "ADX_14": [30.0],
            "ema_20": [102.0],
            "ema_50": [95.0],
            "bb_width": [0.04],
            "bb_width_pct_change": [0.10],
            "atr_percent": [2.0],
            "atr_slope": [0.3],
            "volume_zscore": [0.5],
        })
        
        features = {
            "spread_percent": 0.15,
            "depth_imbalance": 0.25,
        }
        
        scores = scorer.score_regime(df, features)
        
        # Проверяем что features попали в values
        assert "spread_percent" in scores.values
        assert "depth_imbalance" in scores.values
        assert scores.values["spread_percent"] == 0.15
    
    def test_normalize_edge_cases(self, scorer):
        """Тест: граничные случаи нормализации"""
        # Test _normalize directly
        assert scorer._normalize(0, 0, 100) == 0.0
        assert scorer._normalize(100, 0, 100) == 1.0
        assert scorer._normalize(50, 0, 100) == 0.5
        assert scorer._normalize(-10, 0, 100) == 0.0  # Clamp min
        assert scorer._normalize(150, 0, 100) == 1.0  # Clamp max
        
        # Edge: min == max
        result = scorer._normalize(50, 100, 100)
        assert result in [0.0, 1.0]
    
    def test_safe_get_fallback(self, scorer):
        """Тест: безопасное извлечение с fallback"""
        row = pd.Series({
            "adx": 30.0,
            "missing": np.nan,
        })
        
        # Найдено
        assert scorer._safe_get(row, ["adx"], 0.0) == 30.0
        
        # Не найдено → default
        assert scorer._safe_get(row, ["nonexistent"], 99.0) == 99.0
        
        # NaN → default
        assert scorer._safe_get(row, ["missing"], 99.0) == 99.0
        
        # Несколько ключей (fallback chain)
        assert scorer._safe_get(row, ["nonexistent", "adx"], 0.0) == 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
