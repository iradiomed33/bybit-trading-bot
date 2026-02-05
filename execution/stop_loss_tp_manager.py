"""
Менеджер стоп-лоссов и тейк-профитов с привязкой к ATR.

Использует две стратегии:
1. Биржевые SL/TP (reduceOnly) - если поддерживается Bybit API
2. Виртуальные уровни с мониторингом - fallback при частичных заполнениях

Уровни рассчитываются на основе ATR (волатильности), не фиксированных процентов.
"""

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class StopLossTPConfig:
    """Конфигурация стоп-лосса и тейк-профита"""

    # ATR-based расстояния (количество ATR)
    sl_atr_multiplier: float = 1.5  # SL = entry ± 1.5*ATR
    tp_atr_multiplier: float = 2.0  # TP = entry ± 2.0*ATR

    # Если ATR недоступна, используем фиксированные % (fallback)
    sl_percent_fallback: float = 1.0
    tp_percent_fallback: float = 2.0

    # Минимальные расстояния в пунктах (предотвращают слишком близкие уровни)
    min_sl_distance: Decimal = Decimal("10")  # В пунктах (например, 30000 + 10 = 30010)
    min_tp_distance: Decimal = Decimal("20")

    # Режим исполнения
    use_exchange_sl_tp: bool = True  # Попытка использовать биржевые SL/TP (reduceOnly)
    use_virtual_levels: bool = True  # Fallback на виртуальное отслеживание

    # Переквалификация заказов (переместить SL/TP при достижении промежуточных уровней)
    enable_trailing_stop: bool = True
    trailing_multiplier: float = 0.5  # Trailing = 0.5*ATR


@dataclass
class StopLossTakeProfitLevels:
    """Уровни стоп-лосса и тейк-профита для конкретной позиции"""

    position_id: str  # Уникальный ID позиции (order_id)
    symbol: str
    side: str  # "Long" или "Short"
    entry_price: Decimal
    entry_qty: Decimal
    atr: Optional[Decimal]  # Current ATR из рыночных данных

    # Рассчитанные уровни
    sl_price: Decimal
    tp_price: Decimal

    # Статус
    sl_hit: bool = False
    tp_hit: bool = False
    closed_qty: Decimal = Decimal("0")  # Закрытое количество (для partial fills)

    # Биржевые ордера (если используются)
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None

    # Метаданные
    created_at: float = field(default_factory=time.time)
    last_checked_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для БД/логирования"""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "entry_qty": str(self.entry_qty),
            "atr": str(self.atr) if self.atr else None,
            "sl_price": str(self.sl_price),
            "tp_price": str(self.tp_price),
            "sl_hit": self.sl_hit,
            "tp_hit": self.tp_hit,
            "closed_qty": str(self.closed_qty),
            "sl_order_id": self.sl_order_id,
            "tp_order_id": self.tp_order_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopLossTakeProfitLevels":
        """Создать из словаря"""
        return cls(
            position_id=data["position_id"],
            symbol=data["symbol"],
            side=data["side"],
            entry_price=Decimal(str(data["entry_price"])),
            entry_qty=Decimal(str(data["entry_qty"])),
            atr=Decimal(str(data["atr"])) if data.get("atr") else None,
            sl_price=Decimal(str(data["sl_price"])),
            tp_price=Decimal(str(data["tp_price"])),
            sl_hit=data.get("sl_hit", False),
            tp_hit=data.get("tp_hit", False),
            closed_qty=Decimal(str(data.get("closed_qty", "0"))),
            sl_order_id=data.get("sl_order_id"),
            tp_order_id=data.get("tp_order_id"),
        )


class StopLossTakeProfitManager:
    """Управляет SL/TP уровнями для позиций"""

    def __init__(
        self,
        order_manager,  # REST клиент для выставления ордеров
        config: StopLossTPConfig = None,
    ):
        """
        Args:
            order_manager: Менеджер ордеров для выставления SL/TP
            config: Конфигурация SL/TP
        """
        self.order_manager = order_manager
        self.config = config or StopLossTPConfig()

        # Хранилище активных SL/TP
        self._levels: Dict[str, StopLossTakeProfitLevels] = {}

        logger.info(
            f"StopLossTakeProfitManager initialized: "
            f"exchange_sl_tp={self.config.use_exchange_sl_tp}, "
            f"virtual={self.config.use_virtual_levels}"
        )

    def calculate_levels(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: Decimal,
        entry_qty: Decimal,
        current_atr: Optional[Decimal] = None,
    ) -> StopLossTakeProfitLevels:
        """
        Рассчитать SL и TP на основе ATR

        Args:
            position_id: Уникальный ID позиции (обычно order_id)
            symbol: Торговая пара
            side: "Long" или "Short"
            entry_price: Цена входа
            entry_qty: Количество
            current_atr: Текущее значение ATR (может быть None, используем fallback)

        Returns:
            StopLossTakeProfitLevels с рассчитанными уровнями
        """
        entry_price = Decimal(str(entry_price))
        entry_qty = Decimal(str(entry_qty))
        current_atr = Decimal(str(current_atr)) if current_atr else None

        # Рассчитываем расстояния
        if current_atr and current_atr > 0:
            # ATR-based (предпочтительно)
            sl_distance = current_atr * Decimal(str(self.config.sl_atr_multiplier))
            tp_distance = current_atr * Decimal(str(self.config.tp_atr_multiplier))

            logger.info(
                f"[{position_id}] SL/TP calculated with ATR: "
                f"ATR={current_atr}, sl_distance={sl_distance}, tp_distance={tp_distance}"
            )
        else:
            # Fallback к процентам
            sl_distance = entry_price * Decimal(str(self.config.sl_percent_fallback / 100))
            tp_distance = entry_price * Decimal(str(self.config.tp_percent_fallback / 100))

            logger.warning(
                f"[{position_id}] SL/TP calculated with fallback %: "
                f"sl_pct={self.config.sl_percent_fallback}%, "
                f"tp_pct={self.config.tp_percent_fallback}%"
            )

        # Гарантируем минимальные расстояния
        min_sl = self.config.min_sl_distance
        min_tp = self.config.min_tp_distance

        if sl_distance < min_sl:
            sl_distance = min_sl
        if tp_distance < min_tp:
            tp_distance = min_tp

        # Рассчитываем уровни в зависимости от направления
        if side == "Long":
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        else:  # Short
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance

        levels = StopLossTakeProfitLevels(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            entry_qty=entry_qty,
            atr=current_atr,
            sl_price=sl_price,
            tp_price=tp_price,
        )

        self._levels[position_id] = levels

        logger.info(
            f"[{position_id}] SL/TP levels created: "
            f"side={side}, entry={entry_price}, SL={sl_price}, TP={tp_price}"
        )

        return levels

    def place_exchange_sl_tp(
        self, position_id: str, category: str = "linear"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Выставить SL и TP ордера на бирже (reduceOnly)

        Для Bybit v5 это означает использование conditional ордеров
        с triggerDirection и reduceOnly=true

        Args:
            position_id: ID позиции (должна быть в self._levels)
            category: Категория ордера ("linear" для фьючерсов)

        Returns:
            (success: bool, sl_order_id, tp_order_id)
        """
        if position_id not in self._levels:
            logger.error(f"Position {position_id} not found in SL/TP manager")
            return False, None, None

        levels = self._levels[position_id]

        if not self.config.use_exchange_sl_tp:
            logger.debug(f"Exchange SL/TP disabled for {position_id}")
            return True, None, None  # Успешно, но ордера не выставлены (виртуальный режим)

        try:
            # Выставляем SL ордер (conditional, reduceOnly)
            sl_result = self.order_manager.create_order(
                category=category,
                symbol=levels.symbol,
                side="Sell" if levels.side == "Long" else "Buy",  # Противоположное направление
                order_type="Market",
                qty=float(levels.entry_qty),
                reduce_only=True,  # Важно! Только закрытие позиции
                stop_loss=str(levels.sl_price),  # Используем встроенный SL
                trigger_by="LastPrice",
                order_link_id=f"{position_id}_sl",
            )

            if sl_result.get("retCode") != 0:
                logger.warning(
                    f"Failed to place SL order for {position_id}: {sl_result.get('retMsg')}"
                )
                sl_order_id = None
            else:
                sl_order_id = sl_result.get("result", {}).get("orderId")
                levels.sl_order_id = sl_order_id
                logger.info(f"SL order placed: {sl_order_id} @ {levels.sl_price}")

            # Выставляем TP ордер (conditional, reduceOnly)
            tp_result = self.order_manager.create_order(
                category=category,
                symbol=levels.symbol,
                side="Sell" if levels.side == "Long" else "Buy",  # Противоположное направление
                order_type="Market",
                qty=float(levels.entry_qty),
                reduce_only=True,
                take_profit=str(levels.tp_price),  # Используем встроенный TP
                trigger_by="LastPrice",
                order_link_id=f"{position_id}_tp",
            )

            if tp_result.get("retCode") != 0:
                logger.warning(
                    f"Failed to place TP order for {position_id}: {tp_result.get('retMsg')}"
                )
                tp_order_id = None
            else:
                tp_order_id = tp_result.get("result", {}).get("orderId")
                levels.tp_order_id = tp_order_id
                logger.info(f"TP order placed: {tp_order_id} @ {levels.tp_price}")

            return True, sl_order_id, tp_order_id

        except Exception as e:
            logger.error(f"Error placing exchange SL/TP for {position_id}: {e}")
            return False, None, None

    def check_virtual_levels(
        self, position_id: str, current_price: Decimal, current_qty: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить виртуальные SL/TP уровни (для мониторинга и частичных заполнений)

        Используется когда:
        - Биржевые SL/TP не поддерживаются
        - Возникли частичные заполнения (need to update TP)
        - Нужно отслеживать для логирования

        Args:
            position_id: ID позиции
            current_price: Текущая цена
            current_qty: Текущее количество открытой позиции

        Returns:
            (triggered: bool, trigger_type: "sl"|"tp"|None)
        """
        if position_id not in self._levels:
            return False, None

        levels = self._levels[position_id]
        current_price = Decimal(str(current_price))
        current_qty = Decimal(str(current_qty))

        levels.last_checked_at = time.time()

        # Проверяем SL
        if not levels.sl_hit:
            if levels.side == "Long" and current_price <= levels.sl_price:
                levels.sl_hit = True
                logger.warning(
                    f"[{position_id}] SL HIT: Long position, price {current_price} <= SL {levels.sl_price}"
                )
                return True, "sl"

            elif levels.side == "Short" and current_price >= levels.sl_price:
                levels.sl_hit = True
                logger.warning(
                    f"[{position_id}] SL HIT: Short position, price {current_price} >= SL {levels.sl_price}"
                )
                return True, "sl"

        # Проверяем TP
        if not levels.tp_hit:
            if levels.side == "Long" and current_price >= levels.tp_price:
                levels.tp_hit = True
                logger.info(
                    f"[{position_id}] TP HIT: Long position, price {current_price} >= TP {levels.tp_price}"
                )
                return True, "tp"

            elif levels.side == "Short" and current_price <= levels.tp_price:
                levels.tp_hit = True
                logger.info(
                    f"[{position_id}] TP HIT: Short position, price {current_price} <= TP {levels.tp_price}"
                )
                return True, "tp"

        return False, None

    def handle_partial_fill(
        self, position_id: str, filled_qty: Decimal, remaining_qty: Decimal
    ) -> Optional[StopLossTakeProfitLevels]:
        """
        Обновить SL/TP при частичном заполнении позиции

        Для SL: остаётся то же (защищает оставшуюся позицию)
        Для TP: может быть переквалифицирован на меньший уровень (фиксирует прибыль)

        Args:
            position_id: ID позиции
            filled_qty: Заполненное количество
            remaining_qty: Оставшееся количество

        Returns:
            Обновленные уровни или None если позиция не найдена
        """
        if position_id not in self._levels:
            logger.warning(f"Position {position_id} not found for partial fill update")
            return None

        levels = self._levels[position_id]
        filled_qty = Decimal(str(filled_qty))
        remaining_qty = Decimal(str(remaining_qty))

        if remaining_qty <= 0:
            # Позиция полностью закрыта
            logger.info(f"[{position_id}] Position fully closed, remaining_qty={remaining_qty}")
            return levels

        # Обновляем количество
        old_qty = levels.entry_qty
        levels.entry_qty = remaining_qty
        levels.closed_qty = filled_qty

        logger.info(
            f"[{position_id}] Partial fill updated: "
            f"filled={filled_qty}, remaining={remaining_qty}, "
            f"SL still at {levels.sl_price}, TP still at {levels.tp_price}"
        )

        return levels

    def update_trailing_stop(self, position_id: str, current_price: Decimal) -> bool:
        """
        Обновить trailing stop при новом благоприятном ценовом движении

        Args:
            position_id: ID позиции
            current_price: Текущая цена

        Returns:
            True если SL был обновлен
        """
        if not self.config.enable_trailing_stop:
            return False

        if position_id not in self._levels:
            return False

        levels = self._levels[position_id]
        current_price = Decimal(str(current_price))

        if not levels.atr or levels.atr == 0:
            return False

        trailing_distance = levels.atr * Decimal(str(self.config.trailing_multiplier))

        if levels.side == "Long":
            # Для лонга trailing stop движется вверх
            new_sl = current_price - trailing_distance
            if new_sl > levels.sl_price:
                logger.info(
                    f"[{position_id}] Trailing stop updated: {levels.sl_price} → {new_sl}"
                )
                levels.sl_price = new_sl
                return True

        else:  # Short
            # Для шорта trailing stop движется вниз
            new_sl = current_price + trailing_distance
            if new_sl < levels.sl_price:
                logger.info(
                    f"[{position_id}] Trailing stop updated: {levels.sl_price} → {new_sl}"
                )
                levels.sl_price = new_sl
                return True

        return False

    def get_levels(self, position_id: str) -> Optional[StopLossTakeProfitLevels]:
        """Получить текущие SL/TP уровни позиции"""
        return self._levels.get(position_id)

    def close_position_levels(self, position_id: str) -> bool:
        """
        Закрыть SL/TP отслеживание для позиции (при её закрытии)

        Args:
            position_id: ID позиции

        Returns:
            True если позиция была найдена и удалена
        """
        if position_id in self._levels:
            levels = self._levels.pop(position_id)
            logger.info(
                f"[{position_id}] Closed SL/TP tracking: "
                f"sl_hit={levels.sl_hit}, tp_hit={levels.tp_hit}, closed_qty={levels.closed_qty}"
            )
            return True
        return False

    def get_all_active_levels(self) -> Dict[str, StopLossTakeProfitLevels]:
        """Получить все активные SL/TP уровни"""
        return dict(self._levels)

    def cleanup_old_levels(self, age_seconds: int = 86400) -> int:
        """
        Удалить старые завершённые SL/TP записи (старше age_seconds)

        Args:
            age_seconds: Возраст для удаления (секунды)

        Returns:
            Количество удалённых записей
        """
        now = time.time()
        expired_ids = [
            pos_id
            for pos_id, levels in self._levels.items()
            if (levels.sl_hit or levels.tp_hit) and (now - levels.created_at) > age_seconds
        ]

        for pos_id in expired_ids:
            del self._levels[pos_id]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} old SL/TP records")

        return len(expired_ids)
