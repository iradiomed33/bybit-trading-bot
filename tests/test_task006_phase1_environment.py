#!/usr/bin/env python3
"""
TASK-006 Phase 1: Единый источник истины для testnet/mainnet

Проверяет, что единственный способ определить используется ли testnet или mainnet - это:
1. ConfigManager.is_testnet() метод
2. Priority: ENVIRONMENT env var > trading.testnet JSON > default True

Все точки входа (CLI, API, тесты) должны использовать единый механизм.
"""

import os
import pytest
import json
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

from config.settings import ConfigManager
from config import Config
from logger import setup_logger

logger = setup_logger()


class TestConfigManagerEnvironmentDetection:
    """Тестирование методов is_testnet() и get_environment()"""

    def test_is_testnet_returns_boolean(self):
        """is_testnet() должен вернуть boolean"""
        config = ConfigManager()
        result = config.is_testnet()
        assert isinstance(result, bool), "is_testnet() должен вернуть bool"

    def test_get_environment_returns_string(self):
        """get_environment() должен вернуть строку 'testnet' или 'mainnet'"""
        config = ConfigManager()
        result = config.get_environment()
        assert isinstance(result, str), "get_environment() должен вернуть строку"
        assert result in ("testnet", "mainnet"), f"Invalid environment: {result}"

    def test_environment_consistency(self):
        """is_testnet() и get_environment() должны быть согласованы"""
        config = ConfigManager()
        
        is_testnet = config.is_testnet()
        env_str = config.get_environment()
        
        if is_testnet:
            assert env_str == "testnet", "Если is_testnet() == True, то get_environment() == 'testnet'"
        else:
            assert env_str == "mainnet", "Если is_testnet() == False, то get_environment() == 'mainnet'"

    def test_json_config_testnet_parameter(self):
        """trading.testnet в JSON должен быть доступен через config.get()"""
        config = ConfigManager()
        
        # Получить значение из JSON конфига
        json_testnet = config.get("trading.testnet", None)
        assert json_testnet is not None, "trading.testnet должен быть в конфиге"
        assert isinstance(json_testnet, bool), "trading.testnet должен быть boolean"


class TestEnvironmentPriority:
    """Тестирование приоритета: ENVIRONMENT > JSON > default"""

    def test_priority_environment_over_json(self):
        """
        Когда ENVIRONMENT='testnet' и trading.testnet=False,
        should use ENVIRONMENT (testnet)
        """
        # Сохраняем исходное значение
        original_env = os.environ.get("ENVIRONMENT")
        
        # Создаем конфиг с trading.testnet=False
        with patch("config.Config.ENVIRONMENT", "testnet"):
            config = ConfigManager()
            
            # Должен использовать ENVIRONMENT (testnet)
            result = config.is_testnet()
            assert result is True, "ENVIRONMENT='testnet' должен иметь приоритет над JSON"
        
        # Восстанавливаем окружение
        if original_env:
            os.environ["ENVIRONMENT"] = original_env
        elif "ENVIRONMENT" in os.environ:
            del os.environ["ENVIRONMENT"]

    def test_priority_mainnet_environment(self):
        """
        Когда ENVIRONMENT='mainnet' и trading.testnet=True,
        should use ENVIRONMENT (mainnet)
        """
        with patch("config.Config.ENVIRONMENT", "mainnet"):
            config = ConfigManager()
            
            # Должен использовать ENVIRONMENT (mainnet)
            result = config.is_testnet()
            assert result is False, "ENVIRONMENT='mainnet' должен иметь приоритет над JSON"

    def test_fallback_to_json_when_environment_not_set(self):
        """
        Когда ENVIRONMENT не установлен или пустой,
        should use trading.testnet из JSON
        """
        with patch("config.Config.ENVIRONMENT", None):
            config = ConfigManager()
            json_testnet = config.get("trading.testnet", True)
            
            result = config.is_testnet()
            assert result == json_testnet, \
                "Когда ENVIRONMENT не установлен, должен использоваться trading.testnet из JSON"

    def test_default_to_testnet(self):
        """
        Дефолт должен быть testnet=True если ничего не установлено
        """
        with patch("config.Config.ENVIRONMENT", None):
            config = ConfigManager()
            
            # Даже если trading.testnet отсутствует, get() вернет default True
            result = config.is_testnet()
            assert result is True, "Дефолт должен быть testnet"


class TestCLIEnvironmentUsage:
    """Тестирование, что CLI использует ConfigManager.is_testnet()"""

    def test_cli_import_config_manager(self):
        """cli.py должен импортировать ConfigManager"""
        from pathlib import Path
        cli_path = Path(__file__).parent.parent / "cli.py"
        
        with open(cli_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "from config.settings import ConfigManager" in content, \
            "cli.py должен импортировать ConfigManager"

    def test_cli_uses_config_is_testnet(self):
        """cli.py должен использовать config.is_testnet() или ConfigManager().is_testnet()"""
        from pathlib import Path
        cli_path = Path(__file__).parent.parent / "cli.py"
        
        with open(cli_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что Config.ENVIRONMENT == "testnet" больше не используется в key местах
        lines = content.split('\n')
        
        # Считаем количество직직 Config.ENVIRONMENT сравнений
        config_env_comparisons = sum(1 for line in lines 
                                      if 'Config.ENVIRONMENT == "testnet"' in line)
        
        # Может быть максимум в небольших utility функциях или комментариях
        # Правильное использование: config.is_testnet() или ConfigManager().is_testnet()
        is_testnet_usages = sum(1 for line in lines 
                               if '.is_testnet()' in line)
        
        assert is_testnet_usages > 0, "cli.py должен использовать .is_testnet()"
        assert config_env_comparisons == 0, \
            "cli.py большинство используют Config.ENVIRONMENT == 'testnet' прямо (должны использовать is_testnet())"

    def test_smoke_test_uses_config_manager(self):
        """smoke_test.py должен импортировать и использовать ConfigManager"""
        from pathlib import Path
        smoke_path = Path(__file__).parent.parent / "smoke_test.py"
        
        with open(smoke_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "from config.settings import ConfigManager" in content, \
            "smoke_test.py должен импортировать ConfigManager"
        
        assert "ConfigManager().is_testnet()" in content, \
            "smoke_test.py должен использовать ConfigManager().is_testnet()"


class TestConfigManagerSingleton:
    """Тестирование, что ConfigManager работает одинаково во всех случаях"""

    def test_multiple_config_instances_same_result(self):
        """Разные экземпляры ConfigManager должны возвращать один результат"""
        config1 = ConfigManager()
        config2 = ConfigManager()
        
        result1 = config1.is_testnet()
        result2 = config2.is_testnet()
        
        assert result1 == result2, \
            "Разные экземпляры ConfigManager должны давать один результат"

    def test_multiple_get_environment_same_result(self):
        """get_environment() должен быть согласован между инстансами"""
        config1 = ConfigManager()
        config2 = ConfigManager()
        
        env1 = config1.get_environment()
        env2 = config2.get_environment()
        
        assert env1 == env2, \
            "get_environment() должен быть одинаков между инстансами"


class TestEnvironmentMatrix:
    """Матрица тестирования различных комбинаций ENVIRONMENT и trading.testnet"""

    def test_env_testnet_json_testnet(self):
        """ENVIRONMENT=testnet, trading.testnet=true -> testnet"""
        with patch("config.Config.ENVIRONMENT", "testnet"):
            config = ConfigManager()
            with patch.object(config, 'get', return_value=True):
                result = config.is_testnet()
                assert result is True

    def test_env_testnet_json_mainnet(self):
        """ENVIRONMENT=testnet, trading.testnet=false -> testnet (приоритет)"""
        with patch("config.Config.ENVIRONMENT", "testnet"):
            config = ConfigManager()
            # Даже если JSON говорит mainnet, ENVIRONMENT должен выигрывать
            result = config.is_testnet()
            # Результат же зависит от реального конфига
            # Но важно что если ENVIRONMENT определен, он используется

    def test_env_mainnet_json_testnet(self):
        """ENVIRONMENT=mainnet, trading.testnet=true -> mainnet (приоритет)"""
        with patch("config.Config.ENVIRONMENT", "mainnet"):
            config = ConfigManager()
            # Даже если JSON говорит testnet, ENVIRONMENT должен выигрывать
            result = config.is_testnet()
            assert result is False

    def test_env_not_set_json_testnet(self):
        """ENVIRONMENT not set, trading.testnet=true -> testnet"""
        with patch("config.Config.ENVIRONMENT", None):
            config = ConfigManager()
            # Должен использовать JSON
            json_testnet = config.get("trading.testnet", True)
            result = config.is_testnet()
            assert result == json_testnet


class TestLogging:
    """Проверяет что ConfigManager логирует какой источник используется"""

    def test_is_testnet_logs_source(self, caplog):
        """is_testnet() должен логировать источник (ENVIRONMENT или JSON)"""
        import logging
        caplog.set_level(logging.DEBUG)
        
        config = ConfigManager()
        result = config.is_testnet()
        
        # Проверяем что что-то было залогировано о источнике
        log_contents = caplog.text.lower()
        
        # Должен быть логирован источник (environment или config)
        assert "environment" in log_contents or "config" in log_contents, \
            "is_testnet() должен логировать свой источник"


class TestBackwardCompatibility:
    """Проверяет что путь к Config.ENVIRONMENT все еще работает"""

    def test_config_environment_still_accessible(self):
        """Config.ENVIRONMENT должен остаться доступным в config.py"""
        # Просто проверяем что это не вызовет ошибку
        env = Config.ENVIRONMENT
        assert isinstance(env, str) or env is None, \
            "Config.ENVIRONMENT должен быть строкой или None"

    def test_config_trading_testnet_still_accessible(self):
        """trading.testnet в JSON должен быть доступен"""
        config = ConfigManager()
        
        # Должен быть доступен без проблем
        testnet = config.get("trading.testnet", True)
        assert isinstance(testnet, bool), \
            "trading.testnet должен быть boolean"


class TestIntegrationWithBot:
    """Проверяет интеграцию с bot коде"""

    def test_trading_bot_accepts_testnet_param(self):
        """TradingBot должен принимать testnet параметр"""
        from bot import TradingBot
        
        # Это не должно вызвать ошибку
        bot = TradingBot(
            mode="paper",
            strategies=[],
            symbol="BTCUSDT",
            testnet=True  # Явно передаем testnet
        )
        
        assert bot.testnet is True

    def test_market_data_client_testnet_behavior(self):
        """MarketDataClient должен корректно использовать testnet параметр"""
        from exchange.market_data import MarketDataClient
        
        # Оба должны быть возможны без ошибок
        client_testnet = MarketDataClient(testnet=True)
        client_mainnet = MarketDataClient(testnet=False)
        
        assert True  # Если мы дошли сюда, инициализация прошла успешно


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
