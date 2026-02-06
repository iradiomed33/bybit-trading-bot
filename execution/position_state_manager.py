"""

EXE-002: Position State Manager - управление состоянием позиции


Отслеживает:

- Текущий qty (объём позиции)

- Среднюю цену входа

- Ордера (открытые, частично заполненные)

- Partial fills


Корректно обрабатывает:

- Partial fills (заполнение по частям)

- reduceOnly для закрытий (без переворота)

- Reconciliation с биржей

"""


from decimal import Decimal

from typing import Dict, List, Optional, Tuple

from dataclasses import dataclass, field

from datetime import datetime

import logging


logger = logging.getLogger(__name__)


@dataclass
class Order:

    """Представление ордера"""

    order_id: str

    symbol: str

    side: str  # Buy, Sell

    qty: Decimal

    price: Decimal

    filled_qty: Decimal = Decimal("0")

    status: str = "NEW"  # NEW, PARTIALLY_FILLED, FILLED, CANCELLED

    reduce_only: bool = False

    created_at: datetime = field(default_factory=datetime.utcnow)

    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def remaining_qty(self) -> Decimal:
        """Осталось заполнить"""

        return self.qty - self.filled_qty

    @property
    def fill_percent(self) -> float:
        """Процент заполнения"""

        if self.qty == 0:

            return 0.0

        return float(self.filled_qty / self.qty * 100)


@dataclass
class Position:

    """Состояние позиции"""

    symbol: str

    side: str  # Long, Short, None (no position)

    qty: Decimal = Decimal("0")  # Текущий объём

    avg_entry_price: Decimal = Decimal("0")  # Средняя цена входа

    # История

    total_qty_opened: Decimal = Decimal("0")  # Всего куплено/продано

    total_cost: Decimal = Decimal("0")  # Всего потрачено (qty * price)

    # Ордера

    open_orders: List[Order] = field(default_factory=list)

    filled_orders: List[Order] = field(default_factory=list)

    # Timestamps

    opened_at: Optional[datetime] = None

    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_open(self) -> bool:
        """Есть ли открытая позиция"""

        return self.qty > 0

    def pnl_percent(self, current_price: Decimal) -> float:
        """PnL в процентах от входа"""

        if self.qty == 0 or self.avg_entry_price == 0:

            return 0.0

        if self.side == "Long":

            return float((current_price - self.avg_entry_price) / self.avg_entry_price * 100)

        else:  # Short

            return float((self.avg_entry_price - current_price) / self.avg_entry_price * 100)


class PositionStateManager:

    """

    Менеджер состояния позиции с поддержкой partial fills.


    Гарантирует:

    - Корректное отслеживание qty при partial fills

    - reduceOnly для закрытий (без переворота)

    - Reconciliation с данными биржи

    """

    def __init__(self, symbol: str):
        """

        Инициализировать менеджер состояния позиции.


        Args:

            symbol: Торговая пара (e.g., BTCUSDT)

        """

        self.symbol = symbol

        self.position = Position(symbol=symbol, side=None)

        self.order_history: List[Order] = []

        logger.info(f"PositionStateManager initialized for {symbol}")

    def open_position(

        self,

        side: str,

        qty: Decimal,

        entry_price: Decimal,

        order_id: str,

    ) -> None:
        """

        Открыть позицию с начальным ордером.


        Args:

            side: Long или Short

            qty: Количество

            entry_price: Цена входа

            order_id: ID ордера от биржи

        """

        if self.position.is_open():

            logger.warning(f"Position already open for {self.symbol}: {self.position.side}")

            return

        self.position.side = side

        self.position.qty = qty

        self.position.avg_entry_price = entry_price

        self.position.total_qty_opened = qty

        self.position.total_cost = qty * entry_price

        self.position.opened_at = datetime.utcnow()

        self.position.updated_at = datetime.utcnow()

        # Регистрируем ордер

        order = Order(

            order_id=order_id,

            symbol=self.symbol,

            side=side,

            qty=qty,

            price=entry_price,

            filled_qty=qty,

            status="FILLED",

        )

        self.position.filled_orders.append(order)

        self.order_history.append(order)

        logger.info(f"Position opened: {side} {qty} @ {entry_price} (order {order_id})")

    def add_partial_fill(

        self,

        order_id: str,

        fill_qty: Decimal,

        fill_price: Decimal,

        side: str,

    ) -> Tuple[bool, str]:
        """

        Обработать partial fill.


        Правила:

        - Только в направлении текущей позиции (no flip)

        - Обновить среднюю цену

        - Отследить заполненный ордер


        Args:

            order_id: ID ордера

            fill_qty: Заполненное количество

            fill_price: Цена заполнения

            side: Long или Short


        Returns:

            (success, message)

        """

        # Проверяем что это не flip

        if self.position.is_open():

            if (self.position.side == "Long" and side == "Short") or (

                self.position.side == "Short" and side == "Long"

            ):

                # Это редукция, ок

                pass

            elif self.position.side == side:

                # Добавление к позиции, ок

                pass

            else:

                return False, f"Invalid side {side} for position {self.position.side}"

        # Ищем или создаём ордер

        order = None

        for o in self.position.open_orders:

            if o.order_id == order_id:

                order = o

                break

        if not order:

            order = Order(

                order_id=order_id,

                symbol=self.symbol,

                side=side,

                qty=fill_qty,  # Может быть не финальное значение

                price=fill_price,

                filled_qty=fill_qty,

                status="FILLED",

            )

            self.position.open_orders.append(order)

        else:

            order.filled_qty += fill_qty

            order.updated_at = datetime.utcnow()

            if order.filled_qty >= order.qty:

                order.status = "FILLED"

        # Обновляем позицию

        # Если это same side как позиция или позиция еще не открыта - добавляем

        is_adding = (side == self.position.side) or not self.position.is_open()

        if is_adding:

            # Добавление к позиции

            old_qty = self.position.qty

            old_cost = self.position.total_cost

            new_qty = self.position.qty + fill_qty

            new_cost = self.position.total_cost + (fill_qty * fill_price)

            # Обновляем среднюю цену

            if new_qty > 0:

                self.position.avg_entry_price = new_cost / new_qty

                self.position.qty = new_qty

                self.position.total_qty_opened += fill_qty

                self.position.total_cost = new_cost

                logger.info(

                    f"Position added: {fill_qty} @ {fill_price}, "

                    f"avg now {self.position.avg_entry_price}"

                )

        else:

            # Редукция позиции (partial close)

            self.position.qty -= fill_qty

            if self.position.qty <= 0:

                # Позиция закрыта

                self.position.qty = Decimal("0")

                self.position.side = None

                logger.info(f"Position closed: {fill_qty} @ {fill_price}")

            else:

                logger.info(

                    f"Position reduced: {fill_qty} @ {fill_price}, qty now {self.position.qty}"

                )

        self.position.updated_at = datetime.utcnow()

        return True, "Fill processed"

    def close_position(

        self,

        close_qty: Decimal,

        close_price: Decimal,

        order_id: str,

    ) -> Tuple[bool, str]:
        """

        Закрыть позицию (или часть) - с reduceOnly.


        Args:

            close_qty: Количество для закрытия

            close_price: Цена закрытия

            order_id: ID ордера закрытия


        Returns:

            (success, message)

        """

        if not self.position.is_open():

            return False, "No open position to close"

        if close_qty > self.position.qty:

            return False, f"Cannot close {close_qty}, only {self.position.qty} open"

        # Регистрируем ордер закрытия как reduceOnly

        order = Order(

            order_id=order_id,

            symbol=self.symbol,

            side="Sell" if self.position.side == "Long" else "Buy",

            qty=close_qty,

            price=close_price,

            filled_qty=close_qty,

            status="FILLED",

            reduce_only=True,

        )

        # Обновляем позицию

        self.position.qty -= close_qty

        self.position.filled_orders.append(order)

        self.order_history.append(order)

        if self.position.qty <= 0:

            self.position.qty = Decimal("0")

            self.position.side = None

            logger.info(f"Position fully closed: {close_qty} @ {close_price}")

        else:

            logger.info(

                f"Position partially closed: {close_qty} @ {close_price}, qty now {self.position.qty}"

            )

        self.position.updated_at = datetime.utcnow()

        return True, "Position closed"

    def reconcile_with_exchange(

        self,

        exchange_qty: Decimal,

        exchange_avg_price: Decimal,

    ) -> Tuple[bool, str]:
        """

        Reconcile локального состояния с биржей.


        Args:

            exchange_qty: qty с биржи

            exchange_avg_price: avg_price с биржи


        Returns:

            (success, message) - если не совпадает, возвращаем warning

        """

        if self.position.qty != exchange_qty:

            logger.warning(f"Qty mismatch: local {self.position.qty}, exchange {exchange_qty}")

            # Обновляем на данные биржи

            self.position.qty = exchange_qty

        if exchange_qty > 0 and self.position.avg_entry_price != exchange_avg_price:

            logger.warning(

                f"Avg price mismatch: local {self.position.avg_entry_price}, "

                f"exchange {exchange_avg_price}"

            )

            # Обновляем на данные биржи

            self.position.avg_entry_price = exchange_avg_price

        self.position.updated_at = datetime.utcnow()

        return True, "Reconciled"

    def get_position_info(self) -> Dict:
        """Получить информацию о позиции"""

        return {

            "symbol": self.symbol,

            "side": self.position.side,

            "qty": self.position.qty,

            "avg_entry_price": self.position.avg_entry_price,

            "is_open": self.position.is_open(),

            "open_orders": len(self.position.open_orders),

            "filled_orders": len(self.position.filled_orders),

            "opened_at": self.position.opened_at,

            "updated_at": self.position.updated_at,

        }

    def get_orders(self) -> List[Dict]:
        """Получить все ордера"""

        orders = []

        for order in self.order_history:

            orders.append(

                {

                    "order_id": order.order_id,

                    "side": order.side,

                    "qty": order.qty,

                    "filled_qty": order.filled_qty,

                    "price": order.price,

                    "status": order.status,

                    "reduce_only": order.reduce_only,

                    "fill_percent": order.fill_percent,

                }

            )

        return orders
