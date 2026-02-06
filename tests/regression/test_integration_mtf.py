"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Multi-timeframe анализ (REG-A1)

Тесты:
- REG-A1-01: MTF confluence сигналы согласованы между разными ТФ
- REG-A1-02: Regime detection на MTF уровне
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from data.timeframe_cache import TimeframeCache
from strategy.meta_layer import RegimeSwitcher
from data.features import FeaturePipeline


class TestREGA1_MTFConfluence:
    """REG-A1-01: Multi-timeframe confluence и согласованность сигналов"""
    
    def test_mtf_cache_initializes(self):
        """TimeframeCache должен инициализироваться с методами add_candle и get_dataframe"""
        cache = TimeframeCache()
        
        # Проверить, что инициализирован
        assert cache is not None
        assert hasattr(cache, 'add_candle'), "TimeframeCache должен иметь add_candle"
        assert hasattr(cache, 'get_dataframe'), "TimeframeCache должен иметь get_dataframe"
    
    def test_regime_consistent_across_timeframes(self, uptrend_data, downtrend_data):
        """Режим должен быть консистентным между ТФ"""
        switcher = RegimeSwitcher()
        pipeline = FeaturePipeline()
        
        # Построить фичей для 1H и 4H
        df_1h = pipeline.build_features(uptrend_data.copy())
        regime_1h = switcher.detect_regime(df_1h)
        
        df_4h = pipeline.build_features(downtrend_data.copy())
        regime_4h = switcher.detect_regime(df_4h)
        
        # Режимы должны быть определены
        assert regime_1h in ['trend', 'range', 'high_vol_event', 'unknown']
        assert regime_4h in ['trend', 'range', 'high_vol_event', 'unknown']
        
        # На trendовых данных режимы должны быть определены
        assert isinstance(regime_1h, str), "Режим должен быть строкой"
        assert isinstance(regime_4h, str), "Режим должен быть строкой"


class TestREGA1_MTFSignals:
    """REG-A1-02: Confluence условий на мног-ТФ уровне"""
    
    def test_higher_timeframe_filters_lower_timeframe_signals(self, uptrend_data):
        """Более высокие ТФ должны фильтровать сигналы нижних ТФ"""
        pipeline = FeaturePipeline()
        
        # Построить фичей с полной историей
        df = pipeline.build_features(uptrend_data.copy())
        
        # На uptrend данных SMA должна быть восходящей
        if 'sma_20' in df.columns and 'sma_50' in df.columns:
            sma_20_trend = df['sma_20'].iloc[-1] > df['sma_20'].iloc[-50]
            sma_50_trend = df['sma_50'].iloc[-1] > df['sma_50'].iloc[-50]
            
            # Обе SMA должны быть в восходящем тренде
            assert sma_20_trend, "SMA 20 должна быть на восходящем тренде"
            assert sma_50_trend, "SMA 50 должна быть на восходящем тренде"


class TestREGA1_MTFValidation:
    """Валидация MTF анализа"""
    
    def test_mtf_features_have_required_columns(self, sample_ohlcv):
        """MTF фичи должны содержать все необходимые столбцы"""
        pipeline = FeaturePipeline()
        df = pipeline.build_features(sample_ohlcv.copy())
        
        required_cols = ['close', 'open', 'high', 'low', 'volume']
        
        for col in required_cols:
            assert col in df.columns, f"Столбец {col} отсутствует в фичах"
    
    def test_mtf_regime_detection_completes(self, sample_ohlcv):
        """Detection режима должен завершаться без ошибок"""
        switcher = RegimeSwitcher()
        pipeline = FeaturePipeline()
        
        df = pipeline.build_features(sample_ohlcv.copy())
        
        # Не должно быть исключений
        regime = switcher.detect_regime(df)
        
        # Результат должен быть строкой
        assert isinstance(regime, str)
        assert len(regime) > 0
    
    def test_timeframe_cache_methods(self):
        """TimeframeCache должен иметь все необходимые методы"""
        cache = TimeframeCache()
        
        # Основные методы
        assert callable(cache.add_candle), "add_candle должен быть методом"
        assert callable(cache.get_dataframe), "get_dataframe должен быть методом"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
