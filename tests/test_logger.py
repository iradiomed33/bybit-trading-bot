"""
Тесты для модуля logger.py
"""

import logging
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import setup_logger
import config as config_module
Config = config_module.Config


def test_logger_creates_log_directory():
    """Логгер должен создавать директорию для логов"""
    log_dir = Path(Config.LOG_DIR)

    assert log_dir.exists()
    assert log_dir.is_dir()


def test_logger_returns_logger_instance():
    """setup_logger должен возвращать объект Logger"""
    logger = setup_logger("test_logger_instance")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger_instance"


def test_logger_has_handlers():
    """Логгер должен иметь console и file handlers"""
    logger = setup_logger("test_logger_handlers")

    # Должно быть минимум 2 handler'а (console + file)
    assert len(logger.handlers) >= 2

    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" in handler_types
    assert "RotatingFileHandler" in handler_types


def test_logger_can_write():
    """Логгер должен писать сообщения без ошибок"""
    logger = setup_logger("test_logger_write")

    # Не должно быть исключений
    try:
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")
    except Exception as e:
        pytest.fail(f"Logger raised exception: {e}")
