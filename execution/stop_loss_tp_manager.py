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

            "StopLossTakeProfitManager initialized: "

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

        Выставить SL и TP на позицию через Trading Stop API.


        Использует Bybit v5 API /v5/position/trading-stop для установки

        Stop Loss и Take Profit непосредственно на позицию.


        Args:

            position_id: ID позиции (должна быть в self._levels)

            category: Категория ордера ("linear" для фьючерсов)


        Returns:

            (success: bool, sl_order_id, tp_order_id)

            Note: sl_order_id и tp_order_id будут None, т.к. Trading Stop

            не создает отдельные ордера, а устанавливает параметры на позицию.

        """

        if position_id not in self._levels:

            logger.error(f"Position {position_id} not found in SL/TP manager")

            return False, None, None

        levels = self._levels[position_id]

        if not self.config.use_exchange_sl_tp:

            logger.debug(f"Exchange SL/TP disabled for {position_id}")

            return True, None, None  # Успешно, но SL/TP не выставлены (виртуальный режим)

        try:
            # ВАЖНО: Проверяем, что позиция действительно существует на бирже
            # Это предотвращает ошибку "can not set tp/sl/ts for zero position"
            from exchange.account import AccountClient
            
            # Получаем клиента для проверки позиции
            if hasattr(self.order_manager, 'client'):
                try:
                    positions_response = self.order_manager.client.post(
                        "/v5/position/list",
                        params={
                            "category": category,
                            "symbol": levels.symbol,
                        }
                    )
                    
                    # Проверяем, есть ли открытая позиция
                    positions = positions_response.get("result", {}).get("list", [])
                    has_position = False
                    
                    for pos in positions:
                        size = float(pos.get("size", 0))
                        if size > 0:
                            has_position = True
                            break
                    
                    if not has_position:
                        logger.warning(
                            f"[{position_id}] No active position found on exchange for {levels.symbol}. "
                            "Skipping exchange SL/TP and using virtual monitoring instead."
                        )
                        return True, None, None  # Успех (используем виртуальный режим)
                        
                except Exception as e:
                    logger.warning(f"Unable to verify position existence: {e}. Attempting to set SL/TP anyway...")

            # Используем Trading Stop API для установки SL/TP на позицию

            result = self.order_manager.set_trading_stop(

                category=category,

                symbol=levels.symbol,

                position_idx=0,  # 0 для one-way mode (по умолчанию)

                stop_loss=str(levels.sl_price) if levels.sl_price else None,

                take_profit=str(levels.tp_price) if levels.tp_price else None,

                sl_trigger_by="LastPrice",

                tp_trigger_by="LastPrice",

                tpsl_mode="Full",  # Применяем SL/TP ко всей позиции

            )

            if result.success:

                logger.info(

                    f"✓ Trading stop set for {position_id}: "

                    f"SL={levels.sl_price}, TP={levels.tp_price}"

                )

                # Trading Stop не возвращает order IDs, сохраняем position_id как reference

                levels.sl_order_id = f"{position_id}_sl_ts"

                levels.tp_order_id = f"{position_id}_tp_ts"

                return True, levels.sl_order_id, levels.tp_order_id

            else:

                logger.error(

                    f"Failed to set trading stop for {position_id}: {result.error}"

                )

                return False, None, None

        except Exception as e:

            logger.error(f"Error setting trading stop for {position_id}: {e}", exc_info=True)

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

    def update_trailing_stop(self, position_id: str, current_price: Decimal, category: str = "linear") -> bool:
        """

        Обновить trailing stop при новом благоприятном ценовом движении


        Args:

            position_id: ID позиции

            current_price: Текущая цена

            category: Категория ордера ("linear" для фьючерсов)


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

        updated = False

        if levels.side == "Long":

            # Для лонга trailing stop движется вверх

            new_sl = current_price - trailing_distance

            if new_sl > levels.sl_price:

                logger.info(f"[{position_id}] Trailing stop updated: {levels.sl_price} → {new_sl}")

                levels.sl_price = new_sl

                updated = True

        else:  # Short

            # Для шорта trailing stop движется вниз

            new_sl = current_price + trailing_distance

            if new_sl < levels.sl_price:

                logger.info(f"[{position_id}] Trailing stop updated: {levels.sl_price} → {new_sl}")

                levels.sl_price = new_sl

                updated = True

        # Если уровень обновился, обновляем его на бирже
        if updated and self.config.use_exchange_sl_tp:

            success, _, _ = self.update_sl_tp(position_id, category=category)

            if not success:

                logger.warning(f"Failed to update trailing stop on exchange for {position_id}")

                # Откатываем изменение, если не удалось обновить на бирже
                # (в реальности можно оставить виртуальное отслеживание)

        return updated

    def get_levels(self, position_id: str) -> Optional[StopLossTakeProfitLevels]:
        """Получить текущие SL/TP уровни позиции"""

        return self._levels.get(position_id)

    def close_position_levels(self, position_id: str, category: str = "linear") -> bool:
        """

        Закрыть SL/TP отслеживание для позиции (при её закрытии)

        и отменить Trading Stop на бирже.


        Args:

            position_id: ID позиции

            category: Категория ордера ("linear" для фьючерсов)


        Returns:

            True если позиция была найдена и удалена

        """

        if position_id in self._levels:

            levels = self._levels[position_id]

            # Отменяем Trading Stop на бирже, если был установлен

            if self.config.use_exchange_sl_tp and (levels.sl_order_id or levels.tp_order_id):

                try:

                    result = self.order_manager.cancel_trading_stop(

                        category=category,

                        symbol=levels.symbol,

                        position_idx=0,

                    )

                    if result.success:

                        logger.info(f"✓ Trading stop cancelled for {position_id}")

                    else:

                        logger.warning(

                            f"Failed to cancel trading stop for {position_id}: {result.error}"

                        )

                except Exception as e:

                    logger.error(f"Error cancelling trading stop for {position_id}: {e}")

            # Удаляем из памяти

            self._levels.pop(position_id)

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

    def update_sl_tp(
        self, position_id: str, category: str = "linear"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Обновить (re-place) SL/TP на бирже при изменении уровней.

        Используется при trailing stop или изменении позиции.

        Args:
            position_id: ID позиции
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
            return True, None, None

        try:
            # Обновляем Trading Stop на бирже с новыми уровнями
            result = self.order_manager.set_trading_stop(
                category=category,
                symbol=levels.symbol,
                position_idx=0,
                stop_loss=str(levels.sl_price) if levels.sl_price else None,
                take_profit=str(levels.tp_price) if levels.tp_price else None,
                sl_trigger_by="LastPrice",
                tp_trigger_by="LastPrice",
                tpsl_mode="Full",
            )

            if result.success:
                logger.info(
                    f"✓ Trading stop updated for {position_id}: "
                    f"SL={levels.sl_price}, TP={levels.tp_price}"
                )
                return True, levels.sl_order_id, levels.tp_order_id
            else:
                logger.error(
                    f"Failed to update trading stop for {position_id}: {result.error}"
                )
                return False, None, None

        except Exception as e:
            logger.error(f"Error updating trading stop for {position_id}: {e}", exc_info=True)
            return False, None, None
