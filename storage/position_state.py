"""

Управление состоянием позиции и синхронизация с биржей.


Функции:

- Хранение текущего состояния позиции (side, qty, entry, orderId, strategy_id)

- Синхронизация с биржей через /v5/position/list

- Обнаружение расхождений (ручное закрытие, частичное закрытие, изменения)

- Логирование всех изменений для аудита


Документация:

- Bybit Position: https://bybit-exchange.github.io/docs/v5/position

- Risk Limit: https://bybit-exchange.github.io/docs/v5/account/risk-limit

"""


import time

from typing import Dict, Any, Optional, List

from dataclasses import dataclass, asdict

from decimal import Decimal

from enum import Enum

from logger import setup_logger


logger = setup_logger(__name__)


class PositionSide(str, Enum):

    """Сторона позиции"""

    LONG = "Long"

    SHORT = "Short"


@dataclass
class PositionState:

    """

    Состояние открытой позиции.


    Сохраняется локально после открытия ордера и синхронизируется с биржей.

    """

    symbol: str

    side: str  # "Long" или "Short"

    qty: Decimal

    entry_price: Decimal

    order_id: str

    strategy_id: str

    opened_at: int  # Unix timestamp в миллисекундах

    # Опциональные поля для синхронизации

    exchange_qty: Optional[Decimal] = None  # Последнее значение с биржи

    exchange_entry_price: Optional[Decimal] = None

    exchange_updated_at: Optional[int] = None

    mark_price: Optional[Decimal] = None  # Текущая mark price

    pnl: Optional[Decimal] = None  # Unrealized PnL

    pnl_percent: Optional[Decimal] = None

    # Метаданные о синхронизации

    last_sync_at: Optional[int] = None

    sync_count: int = 0

    discrepancy_detected: bool = False

    discrepancy_details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для сохранения"""

        data = asdict(self)

        # Конвертируем Decimal в строку для JSON

        for key in data:

            if isinstance(data[key], Decimal):

                data[key] = str(data[key])

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionState":
        """Создать из словаря"""

        # Конвертируем строки обратно в Decimal

        decimal_fields = [

            "qty",

            "entry_price",

            "exchange_qty",

            "exchange_entry_price",

            "mark_price",

            "pnl",

            "pnl_percent",

        ]

        for field in decimal_fields:

            if field in data and data[field] is not None:

                data[field] = Decimal(str(data[field]))

        return cls(**data)


class PositionStateManager:

    """

    Управление состоянием позиций бота.


    - Хранит локальное состояние позиции

    - Синхронизирует с биржей

    - Обнаруживает расхождения (ручное закрытие, изменения)

    - Логирует все изменения

    """

    def __init__(self, account_client, symbol: str):
        """

        Args:

            account_client: AccountClient instance для получения позиций с биржи

            symbol: Торговый символ (BTCUSDT, ETHUSDT и т.д.)

        """

        self.account_client = account_client

        self.symbol = symbol

        self.position: Optional[PositionState] = None

    def open_position(

        self,

        side: str,

        qty: Decimal,

        entry_price: Decimal,

        order_id: str,

        strategy_id: str,

    ) -> None:
        """

        Зарегистрировать открытие новой позиции.


        Args:

            side: "Long" или "Short"

            qty: Количество (нормализованное)

            entry_price: Цена входа (нормализованная)

            order_id: ID ордера на бирже

            strategy_id: ID стратегии которая открыла позицию

        """

        if self.position is not None:

            logger.warning(

                f"Position already exists for {self.symbol}: {self.position.side} {self.position.qty}. "

                "Cannot open duplicate position."

            )

            return

        self.position = PositionState(

            symbol=self.symbol,

            side=side,

            qty=qty,

            entry_price=entry_price,

            order_id=order_id,

            strategy_id=strategy_id,

            opened_at=int(time.time() * 1000),

        )

        logger.info(

            f"Position opened: {side} {qty} {self.symbol} @ {entry_price} "

            f"(orderId={order_id}, strategy={strategy_id})"

        )

    def close_position(self) -> Optional[PositionState]:
        """

        Закрыть позицию локально.


        Returns:

            Закрытая позиция или None если позиции не было

        """

        if self.position is None:

            logger.debug(f"No position to close for {self.symbol}")

            return None

        closed_position = self.position

        logger.info(

            f"Position closed: {closed_position.side} {closed_position.qty} {self.symbol} "

            f"(opened {(int(time.time() * 1000) - closed_position.opened_at) / 1000:.1f}s ago)"

        )

        self.position = None

        return closed_position

    def has_position(self) -> bool:
        """Проверить есть ли открытая позиция"""

        return self.position is not None

    def get_position(self) -> Optional[PositionState]:
        """Получить текущее состояние позиции"""

        return self.position

    def sync_with_exchange(self) -> bool:
        """

        Синхронизировать состояние позиции с биржей.


        Получает позицию с биржи и проверяет расхождения.


        Returns:

            True если синхронизация успешна, False если ошибка

        """

        if self.position is None:

            logger.debug(f"No position to sync for {self.symbol}")

            return True

        try:

            # Получаем позицию с биржи

            exchange_positions = self.account_client.get_positions(category="linear")

            if exchange_positions.get("retCode") != 0:

                logger.error(

                    f"Failed to get positions from exchange: {exchange_positions.get('retMsg')}"

                )

                return False

            # Ищем нашу позицию в списке

            exchange_position = None

            for pos in exchange_positions.get("result", {}).get("list", []):

                if pos.get("symbol") == self.symbol:

                    exchange_position = pos

                    break

            # Если позиции нет на бирже, но она есть локально - ручное закрытие

            if exchange_position is None:

                if self.position is not None:

                    logger.warning(

                        f"Position closed manually on exchange: {self.position.side} {self.position.qty} "

                        f"{self.symbol} (was opened {int(time.time() * 1000) - self.position.opened_at}ms ago)"

                    )

                    self.position = None

                return True

            # Проверяем расхождения

            self._check_discrepancies(exchange_position)

            # Обновляем информацию с биржи

            self.position.exchange_qty = Decimal(exchange_position.get("size", 0))

            self.position.exchange_entry_price = Decimal(exchange_position.get("avgPrice", 0))

            self.position.exchange_updated_at = int(time.time() * 1000)

            self.position.mark_price = Decimal(exchange_position.get("markPrice", 0))

            self.position.pnl = Decimal(exchange_position.get("unrealPnl", 0))

            # Вычисляем PnL в процентах

            if self.position.entry_price != 0:

                pnl_percent = (

                    self.position.pnl / (self.position.entry_price * self.position.qty)

                ) * 100

                self.position.pnl_percent = pnl_percent

            self.position.last_sync_at = int(time.time() * 1000)

            self.position.sync_count += 1

            logger.debug(

                f"Position synced: {self.position.side} {self.position.exchange_qty} {self.symbol} "

                f"@ {self.position.exchange_entry_price}, PnL: {self.position.pnl} "

                f"({self.position.pnl_percent:.2f}%)"

            )

            return True

        except Exception as e:

            logger.error(f"Error syncing position with exchange: {e}", exc_info=True)

            return False

    def _check_discrepancies(self, exchange_position: Dict[str, Any]) -> None:
        """

        Проверить расхождения между локальным состоянием и биржей.


        Args:

            exchange_position: Данные позиции с биржи

        """

        if self.position is None:

            return

        exchange_qty = Decimal(exchange_position.get("size", 0))

        exchange_side = exchange_position.get("side", "")

        exchange_avg_price = Decimal(exchange_position.get("avgPrice", 0))

        discrepancies = []

        # Проверяем сторону

        if self.position.side.lower() != exchange_side.lower():

            discrepancies.append(

                f"Side mismatch: local={self.position.side}, exchange={exchange_side}"

            )

        # Проверяем количество (допускаем 0.1% погрешность)

        if exchange_qty > 0:

            qty_diff_percent = abs(self.position.qty - exchange_qty) / exchange_qty * 100

            if qty_diff_percent > 0.1:  # 0.1% tolerance

                discrepancies.append(

                    f"Qty mismatch: local={self.position.qty}, exchange={exchange_qty} "

                    f"(diff={qty_diff_percent:.2f}%)"

                )

        # Проверяем цену входа (допускаем 1% погрешность из-за частичных наполнений)

        if exchange_avg_price > 0:

            price_diff_percent = (

                abs(self.position.entry_price - exchange_avg_price) / exchange_avg_price * 100

            )

            if price_diff_percent > 1.0:  # 1% tolerance

                discrepancies.append(

                    f"Entry price mismatch: local={self.position.entry_price}, "

                    f"exchange={exchange_avg_price} (diff={price_diff_percent:.2f}%)"

                )

        if discrepancies:

            self.position.discrepancy_detected = True

            self.position.discrepancy_details = "; ".join(discrepancies)

            logger.warning(

                f"Position discrepancy detected for {self.symbol}: "

                f"{self.position.discrepancy_details}"

            )

        else:

            # Очищаем флаг если расхождений больше нет

            if self.position.discrepancy_detected:

                self.position.discrepancy_detected = False

                self.position.discrepancy_details = ""

                logger.info(f"Position discrepancy resolved for {self.symbol}")

    def validate_position(self) -> tuple[bool, str]:
        """

        Валидировать текущее состояние позиции.


        Returns:

            (is_valid, error_message)

        """

        if self.position is None:

            return True, ""

        # Проверяем критические расхождения

        if self.position.discrepancy_detected:

            if "Side mismatch" in self.position.discrepancy_details:

                return False, f"Critical: {self.position.discrepancy_details}"

            if (

                "Qty mismatch" in self.position.discrepancy_details

                and self.position.exchange_qty is not None

                and self.position.exchange_qty == 0

            ):

                return False, f"Position closed unexpectedly: {self.position.discrepancy_details}"

        return True, ""


class PositionStateStorage:

    """

    Персистентное хранилище состояния позиций в БД.


    Сохраняет историю позиций для анализа и восстановления.

    """

    def __init__(self, db):
        """

        Args:

            db: Database instance

        """

        self.db = db

    def save_position_state(self, position: PositionState) -> bool:
        """

        Сохранить состояние позиции в БД.


        Args:

            position: PositionState для сохранения


        Returns:

            True если успешно, False если ошибка

        """

        try:

            self.db.execute(

                """

                INSERT INTO position_states 

                (symbol, side, qty, entry_price, order_id, strategy_id, opened_at, 

                 exchange_qty, exchange_entry_price, mark_price, pnl, pnl_percent)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                """,

                (

                    position.symbol,

                    position.side,

                    str(position.qty),

                    str(position.entry_price),

                    position.order_id,

                    position.strategy_id,

                    position.opened_at,

                    str(position.exchange_qty) if position.exchange_qty else None,

                    str(position.exchange_entry_price) if position.exchange_entry_price else None,

                    str(position.mark_price) if position.mark_price else None,

                    str(position.pnl) if position.pnl else None,

                    str(position.pnl_percent) if position.pnl_percent else None,

                ),

            )

            logger.debug(f"Position state saved for {position.symbol}")

            return True

        except Exception as e:

            logger.error(f"Error saving position state: {e}")

            return False

    def get_last_position(self, symbol: str) -> Optional[PositionState]:
        """

        Получить последнюю позицию для символа из БД.


        Args:

            symbol: Торговый символ


        Returns:

            PositionState или None если не найдена

        """

        try:

            result = self.db.query(

                "SELECT * FROM position_states WHERE symbol = ? ORDER BY opened_at DESC LIMIT 1",

                (symbol,),

            )

            if result:

                data = dict(result[0])

                return PositionState.from_dict(data)

            return None

        except Exception as e:

            logger.error(f"Error getting last position: {e}")

            return None

    def get_position_history(self, symbol: str, limit: int = 100) -> List[PositionState]:
        """

        Получить историю позиций для символа.


        Args:

            symbol: Торговый символ

            limit: Максимальное количество результатов


        Returns:

            Список PositionState

        """

        try:

            results = self.db.query(

                "SELECT * FROM position_states WHERE symbol = ? ORDER BY opened_at DESC LIMIT ?",

                (symbol, limit),

            )

            positions = [PositionState.from_dict(dict(r)) for r in results]

            return positions

        except Exception as e:

            logger.error(f"Error getting position history: {e}")

            return []
