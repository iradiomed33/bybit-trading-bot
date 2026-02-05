"""
Multi-timeframe cache для хранения данных разных таймфреймов.

Используется для фильтрации сигналов на основе согласованности разных ТФ.
"""

import pandas as pd
from typing import Dict, Optional
from logger import setup_logger

logger = setup_logger(__name__)


class TimeframeCache:
    """Кэш данных для разных таймфреймов"""

    def __init__(self):
        """Инициализация кэша"""
        self.cache: Dict[str, pd.DataFrame] = {}
        logger.info("TimeframeCache initialized")

    def add_candle(self, timeframe: str, candle: Dict) -> None:
        """
        Добавить свечу в кэш для конкретного таймфрейма.

        Args:
            timeframe: Таймфрейм (1, 5, 15, 60, 240, D и т.д.)
            candle: Данные свечи (open, high, low, close, volume и т.д.)
        """
        if timeframe not in self.cache:
            self.cache[timeframe] = pd.DataFrame()

        df = self.cache[timeframe]

        # Если свеча уже существует, обновляем её (в случае обновлений)
        if len(df) > 0 and df.iloc[-1]["timestamp"] == candle.get("timestamp"):
            df.iloc[-1] = candle
        else:
            # Добавляем новую свечу
            df = pd.concat([df, pd.DataFrame([candle])], ignore_index=True)

        # Ограничиваем размер кэша (последние 500 свечей)
        if len(df) > 500:
            df = df.iloc[-500:]

        self.cache[timeframe] = df

    def get_latest(self, timeframe: str) -> Optional[Dict]:
        """
        Получить последнюю свечу для таймфрейма.

        Args:
            timeframe: Таймфрейм

        Returns:
            Данные последней свечи или None
        """
        if timeframe not in self.cache or len(self.cache[timeframe]) == 0:
            return None

        return self.cache[timeframe].iloc[-1].to_dict()

    def get_dataframe(self, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Получить весь DataFrame для таймфрейма.

        Args:
            timeframe: Таймфрейм

        Returns:
            DataFrame или None
        """
        return self.cache.get(timeframe)

    def check_confluence(
        self, timeframe_1m: Dict, timeframe_5m: Optional[Dict], timeframe_15m: Optional[Dict]
    ) -> bool:
        """
        Проверить согласованность сигналов на разных таймфреймах.

        Правило: Сигнал считается валидным, если:
        - 1m: Основной сигнал
        - 5m: Поддерживает направление (ориентир, необязательно)
        - 15m: Фильтр тренда (опциональный)

        Args:
            timeframe_1m: Данные 1m свечи
            timeframe_5m: Данные 5m свечи (опционально)
            timeframe_15m: Данные 15m свечи (опционально)

        Returns:
            True если сигналы согласованы, False иначе
        """
        if not timeframe_1m:
            logger.debug("MTF Check: No 1m data available")
            return False

        # Базовая проверка: на 1m должна быть свеча
        close_1m = timeframe_1m.get("close", 0)
        ema_20_1m = timeframe_1m.get("ema_20", close_1m)

        is_uptrend_1m = close_1m > ema_20_1m
        is_downtrend_1m = close_1m < ema_20_1m
        
        logger.debug(f"MTF Check: 1m trend={'UP' if is_uptrend_1m else 'DOWN' if is_downtrend_1m else 'FLAT'} (close={close_1m:.2f}, ema={ema_20_1m:.2f})")

        # Опциональная проверка 5m
        if timeframe_5m:
            close_5m = timeframe_5m.get("close", 0)
            ema_20_5m = timeframe_5m.get("ema_20", close_5m)

            is_uptrend_5m = close_5m > ema_20_5m
            is_downtrend_5m = close_5m < ema_20_5m
            
            logger.debug(f"MTF Check: 5m trend={'UP' if is_uptrend_5m else 'DOWN' if is_downtrend_5m else 'FLAT'}")

            # Если 1m uptrend, то 5m тоже должна быть в uptrend
            if is_uptrend_1m and not is_uptrend_5m:
                logger.debug("MTF Check: FAILED - 5m not in uptrend (weak signal)")
                return False

            # Если 1m downtrend, то 5m тоже должна быть в downtrend
            if is_downtrend_1m and not is_downtrend_5m:
                logger.debug("MTF Check: FAILED - 5m not in downtrend (weak signal)")
                return False
        else:
            logger.debug("MTF Check: No 5m data (optional)")

        # Опциональная проверка 15m (фильтр волатильности)
        if timeframe_15m:
            vol_regime = timeframe_15m.get("vol_regime", 0)

            # Блокируем торговлю при экстремальной волатильности на 15m
            if vol_regime == 1:  # High volatility
                atr_percent = timeframe_15m.get("atr_percent", 0)
                if atr_percent > 3.0:
                    logger.debug(f"MTF Check: FAILED - 15m high volatility ({atr_percent:.2f}%)")
                    return False
        else:
            logger.debug("MTF Check: No 15m data (optional)")

        logger.debug("MTF Check: PASSED - confluence confirmed")
        return True

    def clear(self) -> None:
        """Очистить весь кэш"""
        self.cache.clear()
        logger.info("Timeframe cache cleared")
