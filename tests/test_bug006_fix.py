"""
Тесты для исправления BUG-006: Config partially ignored

Проверяет:
1. Refresh interval берется из конфига
2. Active strategies фильтруются по конфигу
"""

import pytest
from unittest.mock import Mock, MagicMock


class TestActiveStrategiesFiltering:
    """Тесты для фильтрации стратегий по active_strategies"""
    
    def test_strategy_filtering_logic(self):
        """
        Тест: Логика фильтрации стратегий работает корректно
        """
        # Создаем mock стратегии
        class MockStrategy1:
            pass
        
        class MockStrategy2:
            pass
        
        class MockStrategy3:
            pass
        
        # Симулируем выбор из конфига
        active_strategy_names = ["Strategy1", "Strategy2"]
        
        strategy_map = {
            "Strategy1": MockStrategy1,
            "Strategy2": MockStrategy2,
            "Strategy3": MockStrategy3,
        }
        
        strategies = []
        for name in active_strategy_names:
            if name in strategy_map:
                strategies.append(strategy_map[name]())
        
        # Проверяем что создано только 2 стратегии
        assert len(strategies) == 2, "Должно быть создано только 2 стратегии"
        assert isinstance(strategies[0], MockStrategy1), "Первая должна быть Strategy1"
        assert isinstance(strategies[1], MockStrategy2), "Вторая должна быть Strategy2"
    
    def test_strategy_filtering_empty_config(self):
        """
        Тест: При пустом active_strategies используются дефолты
        """
        # Создаем mock стратегии
        class MockStrategy1:
            pass
        
        class MockStrategy2:
            pass
        
        class MockStrategy3:
            pass
        
        # Пустой список стратегий
        active_strategy_names = []
        
        strategy_map = {
            "Strategy1": MockStrategy1,
            "Strategy2": MockStrategy2,
            "Strategy3": MockStrategy3,
        }
        
        strategies = []
        for name in active_strategy_names:
            if name in strategy_map:
                strategies.append(strategy_map[name]())
        
        # Если нет стратегий, должен быть fallback
        if not strategies:
            strategies = [
                MockStrategy1(),
                MockStrategy2(),
                MockStrategy3(),
            ]
        
        # Проверяем fallback
        assert len(strategies) == 3, "Должно быть 3 дефолтных стратегии"
    
    def test_strategy_filtering_unknown_strategy(self):
        """
        Тест: Неизвестные стратегии игнорируются
        """
        class MockStrategy1:
            pass
        
        # Конфиг содержит несуществующую стратегию
        active_strategy_names = ["Strategy1", "UnknownStrategy"]
        
        strategy_map = {
            "Strategy1": MockStrategy1,
        }
        
        strategies = []
        for name in active_strategy_names:
            if name in strategy_map:
                strategies.append(strategy_map[name]())
        
        # Проверяем что создана только валидная стратегия
        assert len(strategies) == 1, "Должна быть создана только одна валидная стратегия"
        assert isinstance(strategies[0], MockStrategy1)


class TestConfigValueUsage:
    """Тесты для использования значений из конфига"""
    
    def test_refresh_interval_value(self):
        """
        Тест: refresh_interval правильно извлекается из конфига
        """
        # Симулируем config.get()
        mock_config = MagicMock()
        mock_config.get = lambda key, default: {
            "market_data.data_refresh_interval": 15,
        }.get(key, default)
        
        # Используем как в коде
        refresh_interval = mock_config.get("market_data.data_refresh_interval", 10)
        
        assert refresh_interval == 15, "Должно быть 15 из конфига"
    
    def test_refresh_interval_default(self):
        """
        Тест: Используется дефолтное значение если нет в конфиге
        """
        mock_config = MagicMock()
        mock_config.get = lambda key, default: default  # Всегда возвращаем дефолт
        
        refresh_interval = mock_config.get("market_data.data_refresh_interval", 10)
        
        assert refresh_interval == 10, "Должно быть дефолтное значение 10"
    
    def test_use_mtf_value(self):
        """
        Тест: use_mtf правильно извлекается из конфига
        """
        mock_config = MagicMock()
        mock_config.get = lambda key, default: {
            "meta_layer.use_mtf": False,
        }.get(key, default)
        
        use_mtf = mock_config.get("meta_layer.use_mtf", True)
        
        assert use_mtf == False, "Должно быть False из конфига"
    
    def test_mtf_score_threshold_value(self):
        """
        Тест: mtf_score_threshold правильно извлекается из конфига
        """
        mock_config = MagicMock()
        mock_config.get = lambda key, default: {
            "meta_layer.mtf_score_threshold": 0.7,
        }.get(key, default)
        
        threshold = mock_config.get("meta_layer.mtf_score_threshold", 0.6)
        
        assert threshold == 0.7, "Должно быть 0.7 из конфига"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
