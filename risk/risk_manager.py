"""

RISK-001: Risk Management System


Управление риском на уровне торговли:

- Risk per trade (risk_usd = equity * risk_pct)

- Position sizing от stop-distance

- Ограничение leverage/notional/exposure

- Validation всех ордеров перед submission


DoD:

- Любая сделка не превышает risk-лимит в USD

- Reject с понятной причиной при превышении

"""


from decimal import Decimal, ROUND_HALF_UP

from typing import Dict, Optional, Tuple, List

from dataclasses import dataclass

import logging


logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:

    """Лимиты риска для счета"""

    # Основные параметры риска

    risk_percent_per_trade: Decimal = Decimal("1")  # 1% на сделку от equity

    max_leverage: Decimal = Decimal("10")  # Max 10x leverage

    max_notional_usd: Decimal = Decimal("100000")  # Max $100k notional

    max_open_exposure_usd: Decimal = Decimal("50000")  # Max $50k open exposure

    # Защита от черных лебедей

    max_daily_loss_percent: Decimal = Decimal("5")  # Max 5% daily loss

    max_total_open_positions: int = 5  # Max 5 одновременных позиций

    # Минимум止损

    min_stop_distance_percent: Decimal = Decimal("1")  # Min 1% stop distance

    def validate(self) -> Tuple[bool, str]:
        """Проверить корректность лимитов"""

        if self.risk_percent_per_trade <= 0 or self.risk_percent_per_trade > 10:

            return False, "risk_percent_per_trade должен быть 0-10%"

        if self.max_leverage < 1:

            return False, "max_leverage должен быть >= 1"

        if self.max_notional_usd <= 0:

            return False, "max_notional_usd должен быть > 0"

        if self.max_open_exposure_usd <= 0:

            return False, "max_open_exposure_usd должен быть > 0"

        if self.min_stop_distance_percent <= 0 or self.min_stop_distance_percent > 50:

            return False, "min_stop_distance_percent должен быть 0-50%"

        return True, "OK"


@dataclass
class TradeRiskAnalysis:

    """Анализ риска для одной торговли"""

    # Input

    entry_price: Decimal

    stop_loss_price: Decimal

    exit_price: Optional[Decimal] = None  # Для целевого профита

    # Calculations

    stop_distance_pct: Decimal = Decimal("0")  # Расстояние до SL в %

    stop_distance_usd: Decimal = Decimal("0")  # Расстояние в USD на unit

    risk_usd: Decimal = Decimal("0")  # Макс риск на сделку в USD

    position_qty: Decimal = Decimal("0")  # Количество units при данном риске

    notional_value: Decimal = Decimal("0")  # Entry qty * entry price

    required_leverage: Decimal = Decimal("0")  # Нужный leverage

    # Validation

    is_valid: bool = False

    validation_errors: List[str] = None

    def __post_init__(self):

        if self.validation_errors is None:

            self.validation_errors = []

    def has_errors(self) -> bool:

        return len(self.validation_errors) > 0


class RiskManager:

    """

    Менеджер риска для управления сделками.


    Расчеты:

    1. stop_distance_pct = (entry_price - stop_loss) / entry_price * 100

    2. risk_usd = equity * risk_percent / 100

    3. qty = risk_usd / (entry_price - stop_loss)

    4. notional = qty * entry_price

    5. leverage = notional / cash

    """

    def __init__(self, limits: RiskLimits = None):
        """

        Инициализировать менеджер риска.


        Args:

            limits: RiskLimits конфигурация

        """

        self.limits = limits or RiskLimits()

        # Валидировать лимиты

        valid, msg = self.limits.validate()

        if not valid:

            raise ValueError(f"Invalid RiskLimits: {msg}")

        # Статус счета

        self.equity: Decimal = Decimal("0")

        self.cash: Decimal = Decimal("0")

        self.open_positions: Dict[str, Decimal] = {}  # symbol -> qty

        self.daily_loss: Decimal = Decimal("0")  # Убыток за день

        logger.info(

            "RiskManager initialized: "

            f"risk={self.limits.risk_percent_per_trade}%, "

            f"max_leverage={self.limits.max_leverage}x, "

            f"max_notional=${float(self.limits.max_notional_usd):.0f}, "

            f"max_exposure=${float(self.limits.max_open_exposure_usd):.0f}"

        )

    def update_account_state(

        self,

        equity: Decimal,

        cash: Decimal,

        open_positions: Dict[str, Decimal] = None,

        daily_loss: Decimal = Decimal("0"),

    ) -> None:
        """

        Обновить состояние счета.


        Args:

            equity: Текущий equity

            cash: Наличные средства

            open_positions: Открытые позиции {symbol: qty}

            daily_loss: Убыток за день

        """

        self.equity = Decimal(str(equity))

        self.cash = Decimal(str(cash))

        self.open_positions = open_positions or {}

        self.daily_loss = Decimal(str(daily_loss))

    def calculate_position_size(

        self,

        entry_price: Decimal,

        stop_loss_price: Decimal,

    ) -> TradeRiskAnalysis:
        """

        Расчитать размер позиции при заданном entry и SL.


        Args:

            entry_price: Цена входа

            stop_loss_price: Цена стопа


        Returns:

            TradeRiskAnalysis с расчетами

        """

        analysis = TradeRiskAnalysis(

            entry_price=Decimal(str(entry_price)),

            stop_loss_price=Decimal(str(stop_loss_price)),

        )

        # 1. Проверяем stop-loss

        if stop_loss_price >= entry_price:

            analysis.validation_errors.append(

                f"Stop loss {stop_loss_price} не может быть >= entry {entry_price}"

            )

            return analysis

        # 2. Расчитываем stop_distance

        stop_distance = entry_price - stop_loss_price

        analysis.stop_distance_usd = stop_distance

        analysis.stop_distance_pct = (stop_distance / entry_price * Decimal("100")).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        # Проверяем минимальный stop-distance

        if analysis.stop_distance_pct < self.limits.min_stop_distance_percent:

            analysis.validation_errors.append(

                f"Stop distance {analysis.stop_distance_pct}% меньше минимума "

                f"{self.limits.min_stop_distance_percent}%"

            )

        # 3. Расчитываем risk_usd

        analysis.risk_usd = (

            self.equity * self.limits.risk_percent_per_trade / Decimal("100")

        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 4. Расчитываем qty = risk_usd / stop_distance_usd

        if analysis.stop_distance_usd > 0:

            analysis.position_qty = (analysis.risk_usd / analysis.stop_distance_usd).quantize(

                Decimal("0.01"), rounding=ROUND_HALF_UP

            )

        # 5. Расчитываем notional

        analysis.notional_value = (analysis.position_qty * entry_price).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        # 6. Расчитываем required leverage

        if self.cash > 0:

            analysis.required_leverage = (analysis.notional_value / self.cash).quantize(

                Decimal("0.01"), rounding=ROUND_HALF_UP

            )

        analysis.is_valid = len(analysis.validation_errors) == 0

        return analysis

    def validate_order(

        self,

        symbol: str,

        qty: Decimal,

        entry_price: Decimal,

        stop_loss_price: Optional[Decimal] = None,

        side: str = "long",

    ) -> Tuple[bool, str]:
        """

        Валидировать ордер перед submission.


        Args:

            symbol: Торговая пара

            qty: Количество

            entry_price: Цена входа

            stop_loss_price: Цена стопа (опционально)

            side: 'long' или 'short'


        Returns:

            (is_valid, reason)

        """

        qty = Decimal(str(qty))

        entry_price = Decimal(str(entry_price))

        # 1. Проверяем количество

        if qty <= 0:

            return False, f"Qty должен быть > 0, получил {qty}"

        # 2. Проверяем цену

        if entry_price <= 0:

            return False, f"Price должна быть > 0, получила {entry_price}"

        # 3. Проверяем daily loss

        if self.daily_loss >= self.equity * self.limits.max_daily_loss_percent / Decimal("100"):

            return False, (

                f"Daily loss limit достигнут: {float(self.daily_loss):.2f} USD "

                f"(max {float(self.limits.max_daily_loss_percent)}% = "

                f"{float(self.equity * self.limits.max_daily_loss_percent / Decimal('100')):.2f} USD)"

            )

        # 4. Проверяем макс открытых позиций

        if len(self.open_positions) >= self.limits.max_total_open_positions:

            return False, (f"Max open positions {self.limits.max_total_open_positions} уже открыто")

        notional = qty * entry_price

        # 5. Проверяем max notional на одну сделку

        if notional > self.limits.max_notional_usd:

            return False, (

                f"Notional {float(notional):.2f} USD превышает max "

                f"{float(self.limits.max_notional_usd):.2f} USD"

            )

        # 6. Проверяем open exposure

        current_exposure = Decimal("0")

        for sym, pos_qty in self.open_positions.items():

            if sym != symbol:  # Не считаем текущую позицию

                current_exposure += pos_qty * entry_price  # Упрощение (используем текущую цену)

        new_exposure = current_exposure + notional

        if new_exposure > self.limits.max_open_exposure_usd:

            return False, (

                f"Total exposure {float(new_exposure):.2f} USD превышает max "

                f"{float(self.limits.max_open_exposure_usd):.2f} USD "

                f"(current {float(current_exposure):.2f} USD)"

            )

        # 7. Проверяем leverage (если есть stop_loss)

        if stop_loss_price:

            analysis = self.calculate_position_size(entry_price, stop_loss_price)

            if analysis.required_leverage > self.limits.max_leverage:

                return False, (

                    f"Required leverage {float(analysis.required_leverage):.1f}x "

                    f"превышает max {float(self.limits.max_leverage):.1f}x"

                )

            # Проверяем что qty соответствует risk management

            if qty > analysis.position_qty * Decimal("1.1"):  # Допуск 10%

                return False, (

                    f"Qty {float(qty):.2f} превышает recommended {float(analysis.position_qty):.2f} "

                    f"(stop distance {float(analysis.stop_distance_pct):.2f}%, "

                    f"risk ${float(analysis.risk_usd):.2f})"

                )

        # Все проверки пройдены

        return True, "OK"

    def get_recommended_order_info(

        self,

        entry_price: Decimal,

        stop_loss_price: Decimal,

    ) -> Dict:
        """

        Получить рекомендации для ордера.


        Returns:

            Dict с рекомендованными параметрами

        """

        analysis = self.calculate_position_size(entry_price, stop_loss_price)

        # Добавляем дополнительные проверки лимитов

        errors = list(analysis.validation_errors)

        # Проверяем notional лимит

        if analysis.notional_value > self.limits.max_notional_usd:

            errors.append(

                f"Notional {float(analysis.notional_value):.2f} USD превышает max "

                f"{float(self.limits.max_notional_usd):.2f} USD"

            )

        # Проверяем leverage лимит

        if analysis.required_leverage > self.limits.max_leverage:

            errors.append(

                f"Required leverage {float(analysis.required_leverage):.1f}x "

                f"превышает max {float(self.limits.max_leverage):.1f}x"

            )

        return {

            "entry_price": float(entry_price),

            "stop_loss": float(stop_loss_price),

            "stop_distance_pct": float(analysis.stop_distance_pct),

            "stop_distance_usd": float(analysis.stop_distance_usd),

            "risk_usd": float(analysis.risk_usd),

            "recommended_qty": float(analysis.position_qty),

            "notional": float(analysis.notional_value),

            "required_leverage": float(analysis.required_leverage),

            "is_within_limits": len(errors) == 0,

            "errors": errors,

        }

    def get_account_summary(self) -> Dict:
        """Получить summary счета"""

        total_open_notional = Decimal("0")

        for symbol, qty in self.open_positions.items():

            total_open_notional += qty  # Упрощение

        return {

            "equity": float(self.equity),

            "cash": float(self.cash),

            "leverage": float(self.equity / self.cash) if self.cash > 0 else Decimal("0"),

            "open_positions": len(self.open_positions),

            "max_open_positions": self.limits.max_total_open_positions,

            "total_open_exposure_approx": float(total_open_notional),

            "max_open_exposure": float(self.limits.max_open_exposure_usd),

            "daily_loss": float(self.daily_loss),

            "max_daily_loss": float(

                self.equity * self.limits.max_daily_loss_percent / Decimal("100")

            ),

            "risk_per_trade": float(self.limits.risk_percent_per_trade),

        }
