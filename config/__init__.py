"""Config package"""

import os
from dotenv import load_dotenv
from config.settings import ConfigManager, get_config

# Загрузка .env файла
load_dotenv()


class Config:
    """Конфигурация бота из переменных окружения (для обратной совместимости)"""

    # Окружение
    ENVIRONMENT = os.getenv("ENVIRONMENT", "testnet")

    # API ключи Bybit
    BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

    # Логирование
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = "logs"

    # Режим работы
    MODE = os.getenv("MODE", "paper")

    # Базовые URLs (V5 API)
    BYBIT_REST_TESTNET = "https://api-testnet.bybit.com"
    BYBIT_REST_MAINNET = "https://api.bybit.com"
    BYBIT_WS_PUBLIC_TESTNET = "wss://stream-testnet.bybit.com/v5/public/linear"
    BYBIT_WS_PUBLIC_MAINNET = "wss://stream.bybit.com/v5/public/linear"

    @classmethod
    def validate(cls):
        """Проверка обязательных параметров"""
        errors = []

        if cls.ENVIRONMENT not in ["testnet", "mainnet"]:
            errors.append(f"Invalid ENVIRONMENT: {cls.ENVIRONMENT}")

        if cls.MODE not in ["backtest", "paper", "live"]:
            errors.append(f"Invalid MODE: {cls.MODE}")

        if cls.MODE == "live":
            if not cls.BYBIT_API_KEY:
                errors.append("BYBIT_API_KEY required for live mode")
            if not cls.BYBIT_API_SECRET:
                errors.append("BYBIT_API_SECRET required for live mode")

        if errors:
            raise ValueError(f"Config validation errors: {', '.join(errors)}")

        return True

    @classmethod
    def get_rest_url(cls):
        """Получить REST URL в зависимости от окружения"""
        return cls.BYBIT_REST_TESTNET if cls.ENVIRONMENT == "testnet" else cls.BYBIT_REST_MAINNET

    @classmethod
    def get_ws_url(cls):
        """Получить WebSocket URL в зависимости от окружения"""
        return cls.BYBIT_WS_PUBLIC_TESTNET if cls.ENVIRONMENT == "testnet" else cls.BYBIT_WS_PUBLIC_MAINNET


__all__ = ["Config", "ConfigManager", "get_config"]
