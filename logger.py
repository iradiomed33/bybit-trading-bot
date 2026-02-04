"""
Structured logging с ротацией логов.
Логи пишутся в консоль и в файл logs/bot_YYYY-MM-DD.log
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "bybit_bot") -> logging.Logger:
    """
    Создаёт и настраивает логгер с консольным и файловым выводом.

    Args:
        name: имя логгера

    Returns:
        Настроенный логгер
    """
    # Значения по умолчанию (не зависимся от config чтобы избежать циклических импортов)
    log_dir = Path("logs")
    log_level = "INFO"

    # Создаём директорию для логов если её нет
    log_dir.mkdir(exist_ok=True)

    # Имя файла лога с датой
    log_filename = log_dir / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"

    # Создаём логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Формат логов (structured)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # Файловый handler с ротацией (макс 10MB, 5 файлов)
    file_handler = RotatingFileHandler(
        log_filename, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Добавляем handlers если их ещё нет
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
