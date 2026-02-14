"""
Market Structure Analysis - поиск swing levels для умного размещения SL/TP

Модуль находит структурные уровни (swing highs/lows) для размещения стоп-лоссов
за реальными уровнями поддержки/сопротивления вместо механистичных ATR расстояний.
"""

import pandas as pd
from decimal import Decimal
from typing import Optional, List, Tuple
from logger import setup_logger

logger = setup_logger(__name__)


class MarketStructureAnalyzer:
    """Анализатор структуры рынка для умного размещения SL/TP"""
    
    def __init__(self, lookback: int = 20):
        """
        Args:
            lookback: Сколько свечей использовать для поиска swing points
        """
        self.lookback = lookback
    
    def find_swing_low(self, candles: List[dict]) -> Optional[Decimal]:
        """
        Находит последний значимый swing low (локальный минимум)
        
        Swing low = свеча, у которой low ниже чем у соседей с обеих сторон
        
        Args:
            candles: Список свечей (dict с полями: open, high, low, close, timestamp)
        
        Returns:
            Decimal: Цена последнего swing low или None
        """
        if len(candles) < 3:
            logger.warning("Not enough candles for swing low detection")
            return None
        
        # Берем последние lookback свечей
        recent = candles[-self.lookback:] if len(candles) >= self.lookback else candles
        
        # Ищем локальный минимум (цена ниже соседей с обеих сторон)
        for i in range(len(recent) - 2, 0, -1):  # Идем от последней к первой
            curr_low = Decimal(str(recent[i]['low']))
            prev_low = Decimal(str(recent[i-1]['low']))
            
            # Проверяем что есть следующая свеча
            if i + 1 < len(recent):
                next_low = Decimal(str(recent[i+1]['low']))
                
                # Swing low: текущий low ниже соседних
                if curr_low < prev_low and curr_low < next_low:
                    logger.debug(f"Swing low found at index {i}: {curr_low}")
                    return curr_low
        
        # Если не нашли swing low, возвращаем абсолютный минимум
        abs_min = min(Decimal(str(c['low'])) for c in recent)
        logger.debug(f"No swing low found, using absolute min: {abs_min}")
        return abs_min
    
    def find_swing_high(self, candles: List[dict]) -> Optional[Decimal]:
        """
        Находит последний значимый swing high (локальный максимум)
        
        Swing high = свеча, у которой high выше чем у соседей с обеих сторон
        
        Args:
            candles: Список свечей
        
        Returns:
            Decimal: Цена последнего swing high или None
        """
        if len(candles) < 3:
            logger.warning("Not enough candles for swing high detection")
            return None
        
        recent = candles[-self.lookback:] if len(candles) >= self.lookback else candles
        
        # Ищем локальный максимум
        for i in range(len(recent) - 2, 0, -1):
            curr_high = Decimal(str(recent[i]['high']))
            prev_high = Decimal(str(recent[i-1]['high']))
            
            if i + 1 < len(recent):
                next_high = Decimal(str(recent[i+1]['high']))
                
                # Swing high: текущий high выше соседних
                if curr_high > prev_high and curr_high > next_high:
                    logger.debug(f"Swing high found at index {i}: {curr_high}")
                    return curr_high
        
        # Если не нашли, возвращаем абсолютный максимум
        abs_max = max(Decimal(str(c['high'])) for c in recent)
        logger.debug(f"No swing high found, using absolute max: {abs_max}")
        return abs_max
    
    def calculate_structure_based_sl(
        self,
        entry_price: Decimal,
        side: str,
        candles: List[dict],
        atr: Decimal,
        min_atr_distance: float = 1.0,
        max_atr_distance: float = 2.5,
        buffer_percent: float = 0.5,
    ) -> Tuple[Decimal, str]:
        """
        Рассчитывает SL на основе структуры рынка с защитой от stop-hunting
        
        Args:
            entry_price: Цена входа
            side: "Long" или "Short"
            candles: Исторические свечи
            atr: Текущий ATR
            min_atr_distance: Минимальное расстояние в ATR (защита от шума)
            max_atr_distance: Максимальное расстояние в ATR (защита от большого риска)
            buffer_percent: Буфер от уровня в % (защита от stop-hunting)
        
        Returns:
            Tuple[Decimal, str]: (SL цена, причина выбора)
        """
        entry_price = Decimal(str(entry_price))
        atr = Decimal(str(atr))
        
        # 1. Найти структурный уровень
        if side == "Long":
            structure_level = self.find_swing_low(candles)
        else:  # Short
            structure_level = self.find_swing_high(candles)
        
        if structure_level is None:
            # Fallback к стандартному ATR-based SL
            fallback_sl = self._calculate_atr_based_sl(
                entry_price, side, atr, multiplier=1.5
            )
            return fallback_sl, "fallback_atr"
        
        # 2. Добавить buffer против stop-hunting
        # Маркет-мейкеры пробивают уровни на 0.2-0.5%
        buffer = min(
            entry_price * Decimal(str(buffer_percent / 100)),
            atr * Decimal("0.3")  # или 30% от ATR
        )
        
        if side == "Long":
            sl_with_buffer = structure_level - buffer
        else:
            sl_with_buffer = structure_level + buffer
        
        # 3. Проверить адекватность расстояния
        sl_distance = abs(entry_price - sl_with_buffer)
        sl_distance_atr = float(sl_distance / atr)
        
        # Минимум: 1.0 ATR (слишком близко = шум выбьет)
        # Максимум: 2.5 ATR (слишком далеко = большой риск)
        
        if sl_distance_atr < min_atr_distance:
            # Структура слишком близко - используем минимальную дистанцию
            sl_final = self._calculate_atr_based_sl(
                entry_price, side, atr, multiplier=min_atr_distance
            )
            reason = f"structure_too_close_{sl_distance_atr:.2f}atr_using_{min_atr_distance}atr"
            logger.info(
                f"Structure too close ({sl_distance_atr:.2f} ATR < {min_atr_distance}), "
                f"using {min_atr_distance} ATR instead"
            )
            
        elif sl_distance_atr > max_atr_distance:
            # Структура слишком далеко - используем максимальную дистанцию
            sl_final = self._calculate_atr_based_sl(
                entry_price, side, atr, multiplier=max_atr_distance
            )
            reason = f"structure_too_far_{sl_distance_atr:.2f}atr_using_{max_atr_distance}atr"
            logger.info(
                f"Structure too far ({sl_distance_atr:.2f} ATR > {max_atr_distance}), "
                f"using {max_atr_distance} ATR instead"
            )
            
        else:
            # Оптимально - используем структуру + buffer
            sl_final = sl_with_buffer
            reason = f"structure_based_{sl_distance_atr:.2f}atr"
            logger.info(
                f"SL placed behind structure: {sl_distance_atr:.2f} ATR, "
                f"buffer={buffer:.2f}, level={structure_level}"
            )
        
        return sl_final, reason
    
    def _calculate_atr_based_sl(
        self,
        entry_price: Decimal,
        side: str,
        atr: Decimal,
        multiplier: float,
    ) -> Decimal:
        """
        Стандартный ATR-based SL (fallback)
        
        Args:
            entry_price: Цена входа
            side: "Long" или "Short"
            atr: ATR
            multiplier: Множитель ATR
        
        Returns:
            Decimal: SL цена
        """
        distance = atr * Decimal(str(multiplier))
        
        if side == "Long":
            return entry_price - distance
        else:
            return entry_price + distance
