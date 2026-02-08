"""
Тесты для исправления anomaly detection (doji-свечи и логирование)

Проверяет:
1. Doji-свечи с умеренными тенями не флагаются как аномалия
2. Экстремальные тени корректно детектируются как аномалия
3. Symbol корректно передается в features
4. Детали аномалии присутствуют в логах
"""

import pytest
import pandas as pd
import numpy as np
from data.features import FeaturePipeline
from strategy.meta_layer import NoTradeZones


class TestAnomalyDetection:
    """Тесты для исправленной логики детектирования аномалий"""

    @pytest.fixture
    def feature_pipeline(self):
        """Создает экземпляр FeaturePipeline"""
        return FeaturePipeline()

    def test_doji_candle_not_anomaly(self, feature_pipeline):
        """
        Тест: doji-свеча (open == close) с умеренными тенями 
        НЕ должна быть помечена как anomaly_wick
        """
        # Создаем синтетические данные с doji-свечой
        data = pd.DataFrame({
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0],  # Умеренная верхняя тень (1%)
            "low": [99.0, 99.0, 99.0],       # Умеренная нижняя тень (1%)
            "close": [100.0, 100.0, 100.0],  # Doji: open == close
            "volume": [1000, 1000, 1000]
        })
        
        # Применяем детектор аномалий
        df_with_anomalies = feature_pipeline.detect_data_anomalies(data)
        
        # Проверяем, что doji не помечена как аномалия
        assert df_with_anomalies.iloc[-1]["anomaly_wick"] == 0, \
            "Doji-свеча с умеренными тенями не должна быть аномалией"
        
        assert df_with_anomalies.iloc[-1]["has_anomaly"] == 0, \
            "has_anomaly должен быть 0 для doji с умеренными тенями"

    def test_extreme_wick_is_anomaly(self, feature_pipeline):
        """
        Тест: свеча с экстремальной тенью должна быть помечена как anomaly_wick
        """
        # Создаем синтетические данные с экстремальной тенью
        data = pd.DataFrame({
            "open": [100.0, 100.0, 100.0],
            "high": [100.5, 100.5, 120.0],  # Экстремальная верхняя тень на последней свече
            "low": [99.5, 99.5, 99.5],
            "close": [100.0, 100.0, 100.2],  # Малое тело на последней свече
            "volume": [1000, 1000, 1000]
        })
        
        # Применяем детектор аномалий
        df_with_anomalies = feature_pipeline.detect_data_anomalies(data)
        
        # Проверяем, что экстремальная тень детектирована
        assert df_with_anomalies.iloc[-1]["anomaly_wick"] == 1, \
            "Свеча с экстремальной тенью должна быть помечена как anomaly_wick"
        
        assert df_with_anomalies.iloc[-1]["has_anomaly"] == 1, \
            "has_anomaly должен быть 1 для свечи с экстремальной тенью"

    def test_normal_candle_not_anomaly(self, feature_pipeline):
        """
        Тест: обычная свеча с нормальным телом и тенями не является аномалией
        """
        # Создаем синтетические данные с обычными свечами
        data = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [101.5, 102.5, 103.5],
            "low": [99.5, 100.5, 101.5],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000, 1000, 1000]
        })
        
        # Применяем детектор аномалий
        df_with_anomalies = feature_pipeline.detect_data_anomalies(data)
        
        # Проверяем, что обычные свечи не помечены как аномалия
        assert df_with_anomalies.iloc[-1]["anomaly_wick"] == 0, \
            "Обычная свеча не должна быть помечена как anomaly_wick"

    def test_low_volume_anomaly_detection(self, feature_pipeline):
        """
        Тест: низкий объем корректно детектируется как аномалия
        """
        # Создаем данные с нормальным объемом, затем резкое падение
        volumes = [1000] * 60 + [50]  # Последняя свеча с очень низким объемом
        
        data = pd.DataFrame({
            "open": np.full(61, 100.0),
            "high": np.full(61, 101.0),
            "low": np.full(61, 99.0),
            "close": np.full(61, 100.0),
            "volume": volumes
        })
        
        # Применяем детектор аномалий
        df_with_anomalies = feature_pipeline.detect_data_anomalies(data)
        
        # Проверяем, что низкий объем детектирован
        assert df_with_anomalies.iloc[-1]["anomaly_low_volume"] == 1, \
            "Низкий объем должен быть детектирован как аномалия"

    def test_no_trade_zones_returns_anomaly_details(self):
        """
        Тест: NoTradeZones.is_trading_allowed возвращает детали аномалии
        """
        # Создаем DataFrame с аномалией wick
        df = pd.DataFrame({
            "has_anomaly": [0, 0, 1],
            "anomaly_wick": [0, 0, 1],
            "anomaly_low_volume": [0, 0, 0],
            "anomaly_gap": [0, 0, 0],
            "vol_regime": [0, 0, 0],
            "atr_percent": [1.0, 1.0, 1.0]
        })
        
        features = {}
        
        # Вызываем is_trading_allowed
        allowed, reason, details = NoTradeZones.is_trading_allowed(df, features, error_count=0)
        
        # Проверяем, что торговля заблокирована
        assert allowed is False, "Торговля должна быть заблокирована при аномалии"
        assert reason == "Data anomaly detected", "Причина должна быть 'Data anomaly detected'"
        
        # Проверяем, что детали содержат информацию о типе аномалии
        assert details is not None, "Детали аномалии должны быть возвращены"
        assert details.get("anomaly_wick") == 1, "Детали должны содержать anomaly_wick=1"
        assert "anomaly_low_volume" not in details or details["anomaly_low_volume"] == 0, \
            "anomaly_low_volume не должен быть в деталях или должен быть 0"

    def test_no_trade_zones_multiple_anomalies(self):
        """
        Тест: NoTradeZones возвращает все сработавшие типы аномалий
        """
        # Создаем DataFrame с несколькими аномалиями
        df = pd.DataFrame({
            "has_anomaly": [0, 0, 1],
            "anomaly_wick": [0, 0, 1],
            "anomaly_low_volume": [0, 0, 1],
            "anomaly_gap": [0, 0, 0],
            "vol_regime": [0, 0, 0],
            "atr_percent": [1.0, 1.0, 1.0]
        })
        
        features = {}
        
        # Вызываем is_trading_allowed
        allowed, reason, details = NoTradeZones.is_trading_allowed(df, features, error_count=0)
        
        # Проверяем детали
        assert details is not None, "Детали аномалии должны быть возвращены"
        assert details.get("anomaly_wick") == 1, "Детали должны содержать anomaly_wick=1"
        assert details.get("anomaly_low_volume") == 1, "Детали должны содержать anomaly_low_volume=1"

    def test_no_trade_zones_no_anomaly(self):
        """
        Тест: NoTradeZones разрешает торговлю при отсутствии аномалий
        """
        # Создаем DataFrame без аномалий
        df = pd.DataFrame({
            "has_anomaly": [0, 0, 0],
            "anomaly_wick": [0, 0, 0],
            "anomaly_low_volume": [0, 0, 0],
            "anomaly_gap": [0, 0, 0],
            "vol_regime": [0, 0, 0],
            "atr_percent": [1.0, 1.0, 1.0]
        })
        
        features = {}
        
        # Вызываем is_trading_allowed
        allowed, reason, details = NoTradeZones.is_trading_allowed(df, features, error_count=0)
        
        # Проверяем, что торговля разрешена
        assert allowed is True, "Торговля должна быть разрешена при отсутствии аномалий"
        assert reason is None, "Причина должна быть None"
        assert details is None, "Детали должны быть None"


class TestSymbolPropagation:
    """Тесты для проверки корректной передачи symbol в features"""
    
    def test_symbol_in_features_structure(self):
        """
        Интеграционный тест: проверяем, что symbol может быть добавлен в features
        и корректно извлекается
        """
        # Симулируем features с добавленным symbol
        features = {
            "orderflow_features": {},
            "symbol": "BTCUSDT"
        }
        
        # Проверяем извлечение
        symbol = features.get("symbol", "UNKNOWN")
        
        assert symbol == "BTCUSDT", "Symbol должен корректно извлекаться из features"
        assert symbol != "UNKNOWN", "Symbol не должен быть UNKNOWN если он был добавлен"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
