"""

Конфигурация pytest.

Добавляет корневую директорию в sys.path для импорта модулей.

"""


import sys

from pathlib import Path


# Добавляем корневую директорию проекта в Python path

project_root = Path(__file__).parent

sys.path.insert(0, str(project_root))
