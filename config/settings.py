"""
Configuration manager для бота.

Отвечает за:
- Загрузку конфигурации из JSON
- Валидацию параметров
- Обновление конфигурации в runtime
- Предоставление API для доступа к настройкам
"""

import json
import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List

# Используем встроенный logging чтобы избежать циклических импортов
logger = logging.getLogger(__name__)


class ConfigManager:
    """Менеджер конфигурации бота"""

    DEFAULT_CONFIG_PATH = "config/bot_settings.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: Путь к файлу конфигурации (опционально)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: Dict[str, Any] = {}
        self.defaults: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Загрузить конфигурацию из JSON файла"""
        path = Path(self.config_path)

        if not path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            self.config = self._get_default_config()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            logger.info(f"Configuration loaded: {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config JSON: {e}")
            self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Получить конфигурацию по умолчанию"""
        return {
            "trading": {
                "symbol": "BTCUSDT",
                "symbols": ["BTCUSDT"],  # Array of trading pairs
                "mode": "paper",
                "testnet": True,
                "active_strategies": ["TrendPullback", "Breakout", "MeanReversion"],
            },
            "market_data": {
                "kline_interval": "60",
                "kline_limit": 500,
                "orderbook_depth": 50,
                "data_refresh_interval": 12,
                "derivatives": {
                    "fetch_mark_price": True,
                    "fetch_index_price": True,
                    "fetch_open_interest": True,
                    "fetch_funding_rate": True,
                },
            },
            "risk_management": {
                "position_risk_percent": 1.0,
                "max_leverage": 10.0,
                "max_position_size": 0.1,
                "stop_loss_percent": 2.0,
                "take_profit_percent": 5.0,
            },
            "strategies": {
                "TrendPullback": {
                    "enabled": True,
                    "confidence_threshold": 0.6,
                    "min_candles": 20,
                    "lookback": 30,
                },
                "Breakout": {
                    "enabled": True,
                    "confidence_threshold": 0.65,
                    "lookback": 20,
                    "breakout_percent": 0.02,
                },
                "MeanReversion": {
                    "enabled": True,
                    "confidence_threshold": 0.55,
                    "lookback": 30,
                    "std_dev_threshold": 2.0,
                },
            },
            "meta_layer": {
                "use_mtf": True,
                "mtf_timeframes": ["1m", "5m", "15m", "60m", "240m", "D"],
                "volatility_filter_enabled": True,
                "volatility_threshold": 0.02,
                "no_trade_hours": [],
            },
            "execution": {
                "order_type": "limit",
                "time_in_force": "GTC",
                "use_breakeven": True,
                "use_partial_exit": True,
                "partial_exit_percent": 0.5,
            },
            "logging": {
                "level": "INFO",
                "max_log_size_mb": 100,
                "keep_logs_days": 7,
            },
            "api": {
                "retry_max_attempts": 3,
                "retry_backoff_factor": 2.0,
                "retry_initial_delay": 0.5,
                "retry_max_delay": 10.0,
                "request_timeout": 30,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение конфигурации по точке-нотации.

        Args:
            key: Ключ (например "trading.symbol" или "risk_management.position_risk_percent")
            default: Значение по умолчанию если ключ не найден

        Returns:
            Значение конфигурации
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def set(self, key: str, value: Any) -> bool:
        """
        Установить значение конфигурации по точке-нотации.

        Args:
            key: Ключ (например "trading.symbol")
            value: Новое значение

        Returns:
            True если успешно, False если ошибка
        """
        keys = key.split(".")
        config = self.config

        # Навигация к родительскому ключу
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Установка значения
        config[keys[-1]] = value
        logger.info(f"Config updated: {key} = {value}")
        return True

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Получить целый раздел конфигурации.

        Args:
            section: Название раздела (например "risk_management")

        Returns:
            Словарь с конфигурацией раздела
        """
        return self.config.get(section, {})

    def update_section(self, section: str, updates: Dict[str, Any]) -> bool:
        """
        Обновить целый раздел конфигурации.

        Args:
            section: Название раздела
            updates: Словарь с новыми значениями

        Returns:
            True если успешно
        """
        if section not in self.config:
            self.config[section] = {}

        self.config[section].update(updates)
        logger.info(f"Config section '{section}' updated: {updates}")
        return True

    def save(self, path: Optional[str] = None) -> bool:
        """
        Сохранить конфигурацию в файл.

        Args:
            path: Путь для сохранения (если не указан, использует текущий)

        Returns:
            True если успешно, False если ошибка
        """
        save_path = path or self.config_path

        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved: {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def reload(self) -> bool:
        """
        Перезагрузить конфигурацию из файла.

        Returns:
            True если успешно
        """
        try:
            self._load_config()
            logger.info("Configuration reloaded")
            return True
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """
        Сбросить конфигурацию на значения по умолчанию.

        Returns:
            True если успешно
        """
        self.config = self._get_default_config()
        logger.info("Configuration reset to defaults")
        return self.save()

    def to_dict(self) -> Dict[str, Any]:
        """
        Получить полную конфигурацию в виде словаря.

        Returns:
            Копия конфигурации
        """
        return copy.deepcopy(self.config)

    def validate(self) -> tuple[bool, List[str]]:
        """
        Валидировать конфигурацию.

        Returns:
            Кортеж (is_valid, list_of_errors)
        """
        errors = []

        # Проверка обязательных полей
        if not self.get("trading.symbol"):
            errors.append("trading.symbol is required")

        risk_percent = self.get("risk_management.position_risk_percent", 0)
        if not (0 < risk_percent <= 100):
            errors.append("risk_management.position_risk_percent must be between 0 and 100")

        leverage = self.get("risk_management.max_leverage", 0)
        if not (1 <= leverage <= 100):
            errors.append("risk_management.max_leverage must be between 1 and 100")

        if errors:
            logger.error(f"Config validation errors: {errors}")

        return len(errors) == 0, errors


# Глобальный экземпляр конфигурации
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Получить глобальный экземпляр конфигурации.

    Args:
        config_path: Путь к файлу конфигурации (только для первого вызова)

    Returns:
        Экземпляр ConfigManager
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigManager(config_path)

    return _config_instance
