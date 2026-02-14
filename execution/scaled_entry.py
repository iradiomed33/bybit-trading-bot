"""
Scaled Entry Manager - управление набором позиции частями

Реализует стратегию пирамидинга: вход несколькими ордерами вместо одного
для снижения риска плохого входа и усиления работающих трендов.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Dict, Any
import time
from logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class EntryLevel:
    """Уровень входа для scaled entry"""
    
    level_number: int  # Номер уровня (1, 2, 3...)
    percent_of_total: float  # Процент от общей позиции (0-100)
    trigger_condition: str  # Условие входа: "immediate", "confirm_profit", "pullback"
    trigger_value: Optional[float] = None  # Значение триггера (например, 0.5 для 0.5R)
    
    # Статус исполнения
    executed: bool = False
    order_id: Optional[str] = None
    filled_qty: Decimal = Decimal("0")
    filled_price: Optional[Decimal] = None
    timestamp: Optional[float] = None


@dataclass
class ScaledEntryConfig:
    """Конфигурация scaled entry"""
    
    enabled: bool = True
    
    # Профили для разных условий волатильности
    volatility_profiles: Dict[str, List[Dict[str, Any]]] = field(default_factory=lambda: {
        "low": [  # ATR% < 2.0
            {"level": 1, "percent": 60.0, "trigger": "immediate", "value": None},
            {"level": 2, "percent": 40.0, "trigger": "confirm_profit", "value": 0.5},  # +0.5R
        ],
        "medium": [  # ATR% 2.0-5.0
            {"level": 1, "percent": 50.0, "trigger": "immediate", "value": None},
            {"level": 2, "percent": 30.0, "trigger": "pullback", "value": -0.3},  # Откат 0.3 ATR
            {"level": 3, "percent": 20.0, "trigger": "confirm_profit", "value": 0.5},
        ],
        "high": [  # ATR% > 5.0
            {"level": 1, "percent": 40.0, "trigger": "immediate", "value": None},
            {"level": 2, "percent": 30.0, "trigger": "pullback", "value": -0.5},
            {"level": 3, "percent": 20.0, "trigger": "confirm_profit", "value": 0.5},
            {"level": 4, "percent": 10.0, "trigger": "confirm_profit", "value": 1.0},  # +1.0R
        ],
    })
    
    # Таймауты для отмены неисполненных ордеров
    level_timeout_minutes: int = 30  # Отменить ордер если не исполнился за 30 минут
    
    # Минимальный размер одного уровня (в USD)
    min_level_notional: float = 10.0


class ScaledEntryManager:
    """Управляет набором позиции частями"""
    
    def __init__(self, config: ScaledEntryConfig = None):
        """
        Args:
            config: Конфигурация scaled entry
        """
        self.config = config or ScaledEntryConfig()
        
        # Хранилище активных scaled entries
        # key = position_id, value = List[EntryLevel]
        self._active_entries: Dict[str, List[EntryLevel]] = {}
        
        logger.info(
            f"ScaledEntryManager initialized: "
            f"enabled={self.config.enabled}, "
            f"profiles={list(self.config.volatility_profiles.keys())}"
        )
    
    def calculate_entry_levels(
        self,
        position_id: str,
        total_qty: Decimal,
        atr_percent: float,
        entry_price: Decimal,
        atr: Decimal,
        side: str,
    ) -> List[EntryLevel]:
        """
        Рассчитывает уровни входа на основе волатильности
        
        Args:
            position_id: ID позиции
            total_qty: Общее количество для входа
            atr_percent: ATR в процентах от цены
            entry_price: Цена первого входа
            atr: Абсолютное значение ATR
            side: "Long" или "Short"
        
        Returns:
            List[EntryLevel]: Список уровней входа
        """
        if not self.config.enabled:
            # Если scaled entry отключен, возвращаем один уровень
            return [
                EntryLevel(
                    level_number=1,
                    percent_of_total=100.0,
                    trigger_condition="immediate",
                    trigger_value=None,
                )
            ]
        
        # Выбираем профиль на основе волатильности
        if atr_percent < 2.0:
            profile_name = "low"
        elif atr_percent < 5.0:
            profile_name = "medium"
        else:
            profile_name = "high"
        
        profile = self.config.volatility_profiles.get(profile_name, [])
        
        logger.info(
            f"[{position_id}] Using '{profile_name}' volatility profile "
            f"(ATR%={atr_percent:.2f}%)"
        )
        
        # Создаем уровни входа
        entry_levels = []
        total_qty = Decimal(str(total_qty))
        entry_price = Decimal(str(entry_price))
        atr = Decimal(str(atr))
        
        for level_config in profile:
            level_qty = total_qty * Decimal(str(level_config["percent"] / 100))
            
            # Проверка минимального notional
            level_notional = float(level_qty * entry_price)
            if level_notional < self.config.min_level_notional:
                logger.warning(
                    f"Level {level_config['level']} notional too small "
                    f"({level_notional:.2f} < {self.config.min_level_notional}), skipping"
                )
                continue
            
            entry_level = EntryLevel(
                level_number=level_config["level"],
                percent_of_total=level_config["percent"],
                trigger_condition=level_config["trigger"],
                trigger_value=level_config.get("value"),
            )
            
            entry_levels.append(entry_level)
        
        # Сохраняем в активные входы
        self._active_entries[position_id] = entry_levels
        
        logger.info(
            f"[{position_id}] Created {len(entry_levels)} entry levels: "
            f"{[f'L{el.level_number}={el.percent_of_total}%' for el in entry_levels]}"
        )
        
        return entry_levels
    
    def get_next_entry_trigger_price(
        self,
        position_id: str,
        current_price: Decimal,
        entry_price: Decimal,
        atr: Decimal,
        side: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Определяет следующий уровень для входа и его триггерную цену
        
        Args:
            position_id: ID позиции
            current_price: Текущая цена
            entry_price: Цена первого входа
            atr: ATR
            side: "Long" или "Short"
        
        Returns:
            Optional[dict]: {"level": EntryLevel, "trigger_price": Decimal, "action": str}
                           или None если нет следующего уровня
        """
        if position_id not in self._active_entries:
            return None
        
        levels = self._active_entries[position_id]
        
        # Найти первый неисполненный уровень
        next_level = None
        for level in levels:
            if not level.executed:
                next_level = level
                break
        
        if next_level is None:
            logger.debug(f"[{position_id}] All entry levels executed")
            return None
        
        # Рассчитать триггерную цену на основе условия
        trigger_price = None
        action = None
        
        if next_level.trigger_condition == "immediate":
            # Немедленный вход по текущей цене
            trigger_price = current_price
            action = "place_now"
            
        elif next_level.trigger_condition == "confirm_profit":
            # Вход после достижения прибыли N*R
            r_profit = next_level.trigger_value or 0.5
            sl_distance = atr * Decimal("1.5")  # Предполагаем SL = 1.5 ATR
            profit_target = sl_distance * Decimal(str(r_profit))
            
            if side == "Long":
                trigger_price = entry_price + profit_target
                action = "wait_above" if current_price >= trigger_price else "wait"
            else:  # Short
                trigger_price = entry_price - profit_target
                action = "wait_below" if current_price <= trigger_price else "wait"
                
        elif next_level.trigger_condition == "pullback":
            # Вход на откате N*ATR от entry_price
            pullback_atr = next_level.trigger_value or -0.3
            pullback_distance = atr * Decimal(str(abs(pullback_atr)))
            
            if side == "Long":
                # Ждем отката вниз
                trigger_price = entry_price - pullback_distance
                action = "wait_below" if current_price <= trigger_price else "wait"
            else:  # Short
                # Ждем отката вверх
                trigger_price = entry_price + pullback_distance
                action = "wait_above" if current_price >= trigger_price else "wait"
        
        if trigger_price is None:
            logger.warning(
                f"[{position_id}] Unknown trigger condition: "
                f"{next_level.trigger_condition}"
            )
            return None
        
        return {
            "level": next_level,
            "trigger_price": trigger_price,
            "action": action,
        }
    
    def mark_level_executed(
        self,
        position_id: str,
        level_number: int,
        order_id: str,
        filled_qty: Decimal,
        filled_price: Decimal,
    ) -> bool:
        """
        Отмечает уровень как исполненный
        
        Args:
            position_id: ID позиции
            level_number: Номер уровня
            order_id: ID исполненного ордера
            filled_qty: Заполненное количество
            filled_price: Цена заполнения
        
        Returns:
            bool: True если уровень найден и отмечен
        """
        if position_id not in self._active_entries:
            logger.warning(f"[{position_id}] Position not found in active entries")
            return False
        
        levels = self._active_entries[position_id]
        
        for level in levels:
            if level.level_number == level_number:
                level.executed = True
                level.order_id = order_id
                level.filled_qty = Decimal(str(filled_qty))
                level.filled_price = Decimal(str(filled_price))
                level.timestamp = time.time()
                
                logger.info(
                    f"[{position_id}] Level {level_number} executed: "
                    f"qty={filled_qty}, price={filled_price}, order={order_id}"
                )
                return True
        
        logger.warning(
            f"[{position_id}] Level {level_number} not found"
        )
        return False
    
    def get_total_filled_qty(self, position_id: str) -> Decimal:
        """
        Возвращает общее заполненное количество по всем уровням
        
        Args:
            position_id: ID позиции
        
        Returns:
            Decimal: Суммарное количество
        """
        if position_id not in self._active_entries:
            return Decimal("0")
        
        levels = self._active_entries[position_id]
        total = sum(level.filled_qty for level in levels if level.executed)
        
        return Decimal(str(total))
    
    def get_average_entry_price(self, position_id: str) -> Optional[Decimal]:
        """
        Рассчитывает среднюю цену входа с учетом всех исполненных уровней
        
        Args:
            position_id: ID позиции
        
        Returns:
            Optional[Decimal]: Средняя цена или None если нет исполненных уровней
        """
        if position_id not in self._active_entries:
            return None
        
        levels = self._active_entries[position_id]
        executed_levels = [l for l in levels if l.executed and l.filled_price]
        
        if not executed_levels:
            return None
        
        # Взвешенная средняя цена
        total_cost = sum(
            level.filled_qty * level.filled_price
            for level in executed_levels
        )
        total_qty = sum(level.filled_qty for level in executed_levels)
        
        if total_qty == 0:
            return None
        
        avg_price = total_cost / total_qty
        
        logger.debug(
            f"[{position_id}] Average entry price: {avg_price:.2f} "
            f"({len(executed_levels)} levels filled)"
        )
        
        return avg_price
    
    def cleanup_position(self, position_id: str):
        """
        Удаляет данные о позиции (вызывается после закрытия)
        
        Args:
            position_id: ID позиции
        """
        if position_id in self._active_entries:
            del self._active_entries[position_id]
            logger.debug(f"[{position_id}] Cleaned up scaled entry data")
    
    def get_entry_summary(self, position_id: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает сводку по scaled entry
        
        Args:
            position_id: ID позиции
        
        Returns:
            Optional[dict]: Статистика входа
        """
        if position_id not in self._active_entries:
            return None
        
        levels = self._active_entries[position_id]
        executed = [l for l in levels if l.executed]
        pending = [l for l in levels if not l.executed]
        
        return {
            "total_levels": len(levels),
            "executed_levels": len(executed),
            "pending_levels": len(pending),
            "total_filled_qty": float(self.get_total_filled_qty(position_id)),
            "average_entry_price": float(self.get_average_entry_price(position_id) or 0),
            "executed_percentages": [l.percent_of_total for l in executed],
            "pending_percentages": [l.percent_of_total for l in pending],
        }
