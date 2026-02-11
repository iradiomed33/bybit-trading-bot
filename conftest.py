"""

Конфигурация pytest.

Добавляет корневую директорию в sys.path для импорта модулей.

"""


import sys
import os
import pytest

from pathlib import Path


# Добавляем корневую директорию проекта в Python path

project_root = Path(__file__).parent

sys.path.insert(0, str(project_root))


def skip_without_testnet(func):
    """Декоратор для пропуска тестов если нет testnet конфигурации"""
    return pytest.mark.skipif(
        not os.getenv('TESTNET_API_KEY') and not os.getenv('TESTNET_SECRET_KEY'),
        reason="TESTNET_API_KEY or TESTNET_SECRET_KEY не установлены"
    )(func)
