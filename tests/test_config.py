"""
Тесты для модуля config.py
"""

import pytest
from config import Config


def test_config_loads_from_env(monkeypatch):
    """Конфиг должен загружать переменные из окружения"""
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    monkeypatch.setenv("MODE", "paper")

    # Перезагружаем класс Config
    from importlib import reload
    import config

    reload(config)
    from config import Config

    assert Config.ENVIRONMENT == "testnet"
    assert Config.MODE == "paper"


def test_config_defaults():
    """Проверка дефолтных значений"""
    assert Config.LOG_DIR == "logs"
    assert Config.ENVIRONMENT in ["testnet", "mainnet"]


def test_config_get_rest_url():
    """REST URL должен зависеть от окружения"""
    # Сохраняем текущее значение
    original_env = Config.ENVIRONMENT

    # Testnet
    Config.ENVIRONMENT = "testnet"
    assert "testnet" in Config.get_rest_url()

    # Mainnet
    Config.ENVIRONMENT = "mainnet"
    assert "testnet" not in Config.get_rest_url()

    # Восстанавливаем
    Config.ENVIRONMENT = original_env


def test_config_validation_invalid_environment():
    """Валидация должна падать на невалидном окружении"""
    original_env = Config.ENVIRONMENT

    Config.ENVIRONMENT = "invalid"

    with pytest.raises(ValueError, match="Invalid ENVIRONMENT"):
        Config.validate()

    Config.ENVIRONMENT = original_env


def test_config_validation_invalid_mode():
    """Валидация должна падать на невалидном режиме"""
    original_mode = Config.MODE
    original_env = Config.ENVIRONMENT

    Config.MODE = "invalid"
    Config.ENVIRONMENT = "testnet"  # валидное окружение

    with pytest.raises(ValueError, match="Invalid MODE"):
        Config.validate()

    Config.MODE = original_mode
    Config.ENVIRONMENT = original_env


def test_config_validation_live_requires_keys():
    """Live режим требует API ключи"""
    original_mode = Config.MODE
    original_key = Config.BYBIT_API_KEY
    original_secret = Config.BYBIT_API_SECRET
    original_env = Config.ENVIRONMENT

    Config.MODE = "live"
    Config.ENVIRONMENT = "testnet"
    Config.BYBIT_API_KEY = ""
    Config.BYBIT_API_SECRET = ""

    with pytest.raises(ValueError, match="BYBIT_API_KEY required"):
        Config.validate()

    # Восстанавливаем
    Config.MODE = original_mode
    Config.BYBIT_API_KEY = original_key
    Config.BYBIT_API_SECRET = original_secret
    Config.ENVIRONMENT = original_env
