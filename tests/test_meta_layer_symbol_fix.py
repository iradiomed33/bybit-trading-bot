"""
Интеграционный тест для проверки исправления Symbol=UNKNOWN в MetaLayer.

Проверяет:
1. Symbol корректно передается в features перед вызовом get_signal
2. В REJECTED логах Symbol не равен UNKNOWN
3. Детали аномалии присутствуют в values при отклонении
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from strategy.meta_layer import MetaLayer
from data.features import FeaturePipeline


class TestMetaLayerSymbolFix:
    """Интеграционные тесты для исправления Symbol=UNKNOWN"""

    @pytest.fixture
    def feature_pipeline(self):
        """Создает экземпляр FeaturePipeline"""
        return FeaturePipeline()

    @pytest.fixture
    def sample_data_with_anomaly(self):
        """Создает данные с аномалией для тестирования REJECTED логов"""
        # Создаем данные с экстремальной тенью (аномалия) на ПРЕДПОСЛЕДНЕЙ свече
        # т.к. NoTradeZones теперь проверяет последнюю ЗАКРЫТУЮ свечу (iloc[-2])
        data = pd.DataFrame({
            "open": [100.0] * 100,
            "high": [102.0] * 98 + [130.0, 102.0],  # Предпоследняя свеча с экстремальной тенью
            "low": [98.0] * 100,
            "close": [100.0] * 98 + [100.5, 100.0],  # Малое тело на предпоследней свече
            "volume": [1000] * 100
        })
        return data

    @pytest.fixture
    def sample_data_normal(self):
        """Создает нормальные данные без аномалий"""
        data = pd.DataFrame({
            "open": [100.0, 101.0, 102.0] * 40,
            "high": [101.5, 102.5, 103.5] * 40,
            "low": [99.5, 100.5, 101.5] * 40,
            "close": [101.0, 102.0, 103.0] * 40,
            "volume": [1000] * 120
        })
        return data

    def test_get_signal_with_anomaly_logs_correct_symbol(
        self, feature_pipeline, sample_data_with_anomaly
    ):
        """
        Интеграционный тест: при no_trade_zone из-за аномалии,
        в REJECTED логе должен быть корректный Symbol (не UNKNOWN)
        """
        # Подготавливаем данные
        df = feature_pipeline.build_features(sample_data_with_anomaly)
        
        # Создаем features с symbol (как в TradingBot)
        features = {"symbol": "BTCUSDT"}
        
        # Создаем MetaLayer с пустым списком стратегий
        with patch('strategy.meta_layer.signal_logger') as mock_logger:
            meta_layer = MetaLayer(strategies=[])
            
            # Вызываем get_signal - должен быть заблокирован из-за аномалии
            result = meta_layer.get_signal(df, features, error_count=0)
            
            # Проверяем, что сигнал не создан (торговля заблокирована)
            assert result is None, "Сигнал должен быть None при аномалии"
            
            # Проверяем, что log_signal_rejected был вызван
            assert mock_logger.log_signal_rejected.called, \
                "log_signal_rejected должен быть вызван при блокировке"
            
            # Получаем аргументы вызова
            call_args = mock_logger.log_signal_rejected.call_args
            
            # Проверяем Symbol
            assert call_args[1]["symbol"] == "BTCUSDT", \
                "Symbol должен быть BTCUSDT, а не UNKNOWN"
            
            assert call_args[1]["symbol"] != "UNKNOWN", \
                "Symbol не должен быть UNKNOWN"
            
            # Проверяем, что детали аномалии присутствуют в values
            values = call_args[1]["values"]
            assert "anomaly_wick" in values or "anomaly_low_volume" in values, \
                "Детали аномалии должны быть в values"

    def test_features_with_symbol_propagation(self):
        """
        Тест проверяет, что symbol корректно добавляется в features
        (имитация того, что делает TradingBot)
        """
        # Имитируем процесс в TradingBot
        symbol = "ETHUSDT"
        
        # Создаем пустой features dict
        features = {}
        
        # Добавляем symbol (как в исправленном trading_bot.py)
        features["symbol"] = symbol
        
        # Проверяем, что symbol доступен
        extracted_symbol = features.get("symbol", "UNKNOWN")
        
        assert extracted_symbol == "ETHUSDT", \
            "Symbol должен корректно извлекаться из features"
        assert extracted_symbol != "UNKNOWN", \
            "Symbol не должен быть UNKNOWN после добавления"

    def test_no_trade_zones_integration_with_details(self, feature_pipeline):
        """
        Интеграционный тест: NoTradeZones возвращает детали аномалии,
        которые затем попадают в лог
        """
        # Создаем данные с несколькими типами аномалий на ПРЕДПОСЛЕДНЕЙ свече
        # т.к. NoTradeZones теперь проверяет последнюю ЗАКРЫТУЮ свечу (iloc[-2])
        data = pd.DataFrame({
            "open": [100.0] * 60 + [100.0, 100.0],
            "high": [101.0] * 60 + [125.0, 101.0],  # Экстремальная тень на предпоследней
            "low": [99.0] * 60 + [99.0, 99.0],
            "close": [100.0] * 60 + [100.1, 100.0],
            "volume": [1000] * 60 + [50, 1000]     # Низкий объем на предпоследней
        })
        
        df = feature_pipeline.build_features(data)
        features = {"symbol": "BTCUSDT"}
        
        # Создаем экземпляр NoTradeZones
        from strategy.meta_layer import NoTradeZones
        
        # Вызываем is_trading_allowed
        allowed, reason, details = NoTradeZones.is_trading_allowed(
            df, features, error_count=0
        )
        
        # Проверяем результат
        assert allowed is False, "Торговля должна быть заблокирована"
        assert reason == "Data anomaly detected", \
            "Причина должна быть 'Data anomaly detected'"
        
        # Проверяем детали
        assert details is not None, "Детали должны быть возвращены"
        assert isinstance(details, dict), "Детали должны быть словарем"
        
        # Должна быть хотя бы одна аномалия
        has_any_anomaly = (
            details.get("anomaly_wick") == 1 or
            details.get("anomaly_low_volume") == 1 or
            details.get("anomaly_gap") == 1
        )
        assert has_any_anomaly, \
            "Детали должны содержать хотя бы один тип аномалии"

    def test_normal_trading_no_details(self, feature_pipeline, sample_data_normal):
        """
        Тест: при нормальной торговле (нет аномалий) details должны быть None
        """
        df = feature_pipeline.build_features(sample_data_normal)
        features = {"symbol": "BTCUSDT"}
        
        from strategy.meta_layer import NoTradeZones
        
        # Вызываем is_trading_allowed
        allowed, reason, details = NoTradeZones.is_trading_allowed(
            df, features, error_count=0
        )
        
        # При нормальных условиях
        assert allowed is True, "Торговля должна быть разрешена"
        assert reason is None, "Причина должна быть None"
        assert details is None, "Детали должны быть None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
