"""

Position Sizing: расчёт размера позиции на основе риска.


Принцип: никогда не рискуем больше X% капитала на одну сделку.

"""


from typing import Dict, Any

from logger import setup_logger


logger = setup_logger(__name__)


class PositionSizer:

    """Расчёт размера позиции с учётом риска"""

    def __init__(self, risk_per_trade_percent: float = 1.0, max_leverage: float = 10.0):
        """

        Args:

            risk_per_trade_percent: Максимальный риск на сделку (% от капитала)

            max_leverage: Максимальное плечо

        """

        self.risk_per_trade_percent = risk_per_trade_percent

        self.max_leverage = max_leverage

        logger.info(

            f"PositionSizer initialized: risk={risk_per_trade_percent}%, "

            f"max_leverage={max_leverage}x"

        )

    def calculate_position_size(

        self,

        account_balance: float,

        entry_price: float,

        stop_loss_price: float,

        side: str = "Buy",

    ) -> Dict[str, Any]:
        """

        Рассчитать размер позиции на основе риска.


        Формула:

        Risk Amount = Account Balance × Risk %

        Position Size = Risk Amount / (Entry Price - Stop Loss Price)


        Args:

            account_balance: Баланс аккаунта (в USDT)

            entry_price: Цена входа

            stop_loss_price: Цена стоп-лосса

            side: Сторона ('Buy' или 'Sell')


        Returns:

            Dict с размером позиции и метаданными

        """

        if account_balance <= 0:

            logger.error("Invalid account balance")

            return {"success": False, "error": "Invalid account balance"}

        if entry_price <= 0 or stop_loss_price <= 0:

            logger.error("Invalid prices")

            return {"success": False, "error": "Invalid prices"}

        # Расстояние до стопа (в абсолютных единицах)

        stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance <= 0:

            logger.error("Stop loss too close to entry")

            return {"success": False, "error": "Invalid stop loss"}

        # Сумма риска в USDT

        risk_amount = account_balance * (self.risk_per_trade_percent / 100)

        # Размер позиции в базовой валюте (например BTC)

        position_size = risk_amount / stop_distance

        # Стоимость позиции в USDT (notional value)

        position_value = position_size * entry_price

        # Требуемое плечо

        required_leverage = position_value / account_balance

        # Проверка максимального плеча

        if required_leverage > self.max_leverage:

            # Уменьшаем позицию до макс. плеча

            position_value = account_balance * self.max_leverage

            position_size = position_value / entry_price

            required_leverage = self.max_leverage

            logger.warning(f"Position size reduced due to max leverage: {required_leverage:.2f}x")

        # Risk/Reward (если потенциальная прибыль известна)

        risk_percent = (stop_distance / entry_price) * 100

        result = {

            "success": True,

            "position_size": round(position_size, 8),  # Округляем для биржи

            "position_value": round(position_value, 2),

            "required_leverage": round(required_leverage, 2),

            "risk_amount": round(risk_amount, 2),

            "risk_percent": round(risk_percent, 4),

            "stop_distance": round(stop_distance, 2),

        }

        logger.debug(

            f"Position calculated: size={result['position_size']}, "

            f"value=${result['position_value']}, leverage={result['required_leverage']}x"

        )

        return result

    def adjust_for_tick_size(

        self, position_size: float, tick_size: float, qty_step: float

    ) -> float:
        """

        Скорректировать размер позиции согласно tick_size и qty_step биржи.


        Args:

            position_size: Рассчитанный размер

            tick_size: Минимальный шаг цены

            qty_step: Минимальный шаг количества


        Returns:

            Скорректированный размер

        """

        # Округляем до ближайшего кратного qty_step

        adjusted_size = round(position_size / qty_step) * qty_step

        logger.debug(f"Position adjusted: {position_size} -> {adjusted_size} (step={qty_step})")

        return adjusted_size
