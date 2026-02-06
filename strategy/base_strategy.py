"""

Базовый класс для всех торговых стратегий.

Обеспечивает единый интерфейс для генерации сигналов.

"""


from abc import ABC, abstractmethod

from typing import Dict, Any, Optional

import pandas as pd

from logger import setup_logger


logger = setup_logger(__name__)


class BaseStrategy(ABC):

    """Абстрактный базовый класс для стратегий"""

    def __init__(self, name: str):
        """

        Args:

            name: Название стратегии

        """

        self.name = name

        self.is_enabled = True

        logger.info(f"Strategy '{name}' initialized")

    @abstractmethod
    def generate_signal(

        self, df: pd.DataFrame, features: Dict[str, Any]

    ) -> Optional[Dict[str, Any]]:
        """

        Генерировать торговый сигнал.


        Args:

            df: DataFrame с OHLCV и признаками

            features: Дополнительные признаки (orderbook, derivatives)


        Returns:

            Dict с сигналом или None (структурированный результат):

            {

                "signal": "long" | "short" | "close",

                "confidence": 0.0-1.0,

                "reasons": [str, ...],

                "values": {"indicator": value, ...},

                "entry_price": float,

                "stop_loss": float,

                "take_profit": float (optional),

                "reason": str (legacy, optional),

                "metadata": dict (legacy, optional)

            }

        """

        pass

    def enable(self):
        """Включить стратегию"""

        self.is_enabled = True

    def disable(self):
        """Выключить стратегию"""

        self.is_enabled = False
