"""

RISK-002: Anti-tail Circuit Breaker


Защита от хвостовых событий:

1. Волатильность: If ATR/range > X нормы → stop trading на N минут

2. Убытки: If N убытков подряд / дневной лимит → kill switch

3. Kill switch: Закрывает все позиции, отменяет ордера, блокирует новые


Триггеры:

- Серия убыточных сделок (N подряд в окне времени)

- Дневной лимит убытка (% от equity)

- Волатильность: ATR > threshold

- Потеря синхронизации

- Деградация данных (WS отвал)

- Резкий рост спреда

"""


from dataclasses import dataclass, field

from decimal import Decimal

from datetime import datetime, timedelta

from typing import Optional, List, Dict

from enum import Enum

import logging


logger = logging.getLogger(__name__)


class CircuitState(Enum):

    """Состояние circuit breaker"""

    ACTIVE = "active"  # Нормальная работа

    VOLATILITY_HALT = "volatility_halt"  # Стоп из-за волатильности

    LOSS_STREAK_ALERT = "loss_streak_alert"  # Серия убытков (alert, еще не kill)

    KILL_SWITCH = "kill_switch"  # Kill switch активирован


@dataclass
class VolatilitySettings:

    """Параметры детекции волатильности"""

    atr_multiplier: Decimal = Decimal("2.0")  # ATR > mean_atr * 2.0

    volatility_lookback_candles: int = 20  # Сколько свечей смотрим (mean ATR)

    halt_duration_minutes: int = 30  # Стоп trading на N минут

    volatility_threshold_percent: Decimal = Decimal("50")  # ATR > mean_atr * (1 + 50%)


@dataclass
class LossStreakSettings:

    """Параметры детекции серии убытков"""

    consecutive_losses_threshold: int = 3  # Kill switch после N убытков

    time_window_minutes: int = 60  # На каком окне смотрим

    alert_on_losses: int = 2  # Alert после N убытков (< kill_switch)

    daily_loss_kill_percent: Decimal = Decimal("5")  # Kill switch если дневной убыток > 5%

    max_spread_percent: float = 1.0  # Макс. допустимый спред (%)

    data_timeout_seconds: int = 60  # Таймаут без данных (сек)


@dataclass
class CircuitBreakerConfig:

    """Конфигурация circuit breaker"""

    volatility_settings: VolatilitySettings = field(default_factory=VolatilitySettings)

    loss_streak_settings: LossStreakSettings = field(default_factory=LossStreakSettings)

    enabled: bool = True


@dataclass
class CircuitBreakerEvent:

    """Событие circuit breaker"""

    timestamp: datetime

    state: CircuitState

    reason: str

    details: Dict = field(default_factory=dict)


class CircuitBreaker:

    """Anti-tail circuit breaker для защиты от экстремальных событий"""

    def __init__(self, config: CircuitBreakerConfig = None):
        """

        Инициализировать circuit breaker


        Args:

            config: Конфигурация (если не передана - используются дефолты)

        """

        self.config = config or CircuitBreakerConfig()

        self.current_state = CircuitState.ACTIVE

        self.state_timestamp: Optional[datetime] = None

        self.recovery_timestamp: Optional[datetime] = None

        # История ATR для детекции волатильности

        self.atr_history: List[Decimal] = []

        # История убытков

        self.loss_history: List[Dict] = (

            []

        )  # [{"timestamp": dt, "loss": Decimal, "pnl": Decimal}, ...]

        # События

        self.events: List[CircuitBreakerEvent] = []

        # Kill switch data

        self.kill_switch_data: Dict = {}

        # Legacy поля для совместимости

        self.is_circuit_broken = False

        self.break_reason = None

        self.consecutive_losses = 0

        self.last_data_timestamp = datetime.now()

        logger.info("CircuitBreaker initialized with RISK-002 anti-tail protection")

    def check_consecutive_losses(self, last_trade_result: str):
        """

        LEGACY: Проверка серии убыточных сделок.


        Args:

            last_trade_result: 'win' или 'loss'

        """

        if last_trade_result == "loss":

            self.consecutive_losses += 1

            logger.warning(f"Consecutive losses: {self.consecutive_losses}")

        else:

            self.consecutive_losses = 0

    def update_volatility(self, current_atr: Decimal) -> None:
        """

        Обновить историю ATR


        Args:

            current_atr: Текущее значение ATR

        """

        if not isinstance(current_atr, Decimal):

            current_atr = Decimal(str(current_atr))

        self.atr_history.append(current_atr)

        # Держим только нужное количество свечей

        if len(self.atr_history) > self.config.volatility_settings.volatility_lookback_candles:

            self.atr_history.pop(0)

    def check_volatility(self) -> tuple[bool, Optional[str]]:
        """

        Проверить волатильность


        Returns:

            (is_spike, reason)

        """

        if not self.config.volatility_settings or len(self.atr_history) < 2:

            return False, None

        current_atr = self.atr_history[-1]

        mean_atr = sum(self.atr_history) / len(self.atr_history)

        # Проверка 1: ATR > mean_atr * multiplier (приоритет выше)

        if self.config.volatility_settings.atr_multiplier > 0:

            threshold_mult = mean_atr * self.config.volatility_settings.atr_multiplier

            if current_atr > threshold_mult:

                reason = (

                    f"ATR spike detected: {current_atr:.4f} > "

                    f"threshold {threshold_mult:.4f} (mean {mean_atr:.4f})"

                )

                return True, reason

        # Проверка 2: ATR > mean_atr * (1 + threshold_percent) (если multiplier не сработала)

        if self.config.volatility_settings.volatility_threshold_percent > 0:

            threshold_pct = mean_atr * (

                Decimal("1")

                + self.config.volatility_settings.volatility_threshold_percent / Decimal("100")

            )

            if current_atr > threshold_pct:

                reason = (

                    f"High volatility: {current_atr:.4f} > "

                    f"threshold {threshold_pct:.4f} (mean + {self.config.volatility_settings.volatility_threshold_percent}%)"

                )

                return True, reason

        return False, None

    def record_loss(self, loss_amount: Decimal, pnl: Decimal = None) -> None:
        """

        Записать убыток


        Args:

            loss_amount: Размер убытка (positive = loss)

            pnl: Полный PnL (может быть отрицательным)

        """

        if not isinstance(loss_amount, Decimal):

            loss_amount = Decimal(str(loss_amount))

        if pnl and not isinstance(pnl, Decimal):

            pnl = Decimal(str(pnl))

        self.loss_history.append(

            {

                "timestamp": datetime.utcnow(),

                "loss": loss_amount,

                "pnl": pnl or -loss_amount,

            }

        )

    def check_loss_streak(self, equity: Decimal = None) -> tuple[bool, Optional[str]]:
        """

        Проверить серию убытков или дневной лимит


        Args:

            equity: Текущий equity (для расчета % от счета)


        Returns:

            (should_trigger_kill, reason)

        """

        if not self.config.loss_streak_settings or not self.loss_history:

            return False, None

        now = datetime.utcnow()

        window_start = now - timedelta(minutes=self.config.loss_streak_settings.time_window_minutes)

        # Получить убытки в окне

        recent_losses = [loss for loss in self.loss_history if loss["timestamp"] >= window_start]

        # Проверка 1: Серия убытков подряд

        consecutive_count = len(recent_losses)

        if consecutive_count >= self.config.loss_streak_settings.consecutive_losses_threshold:

            reason = (

                f"Loss streak triggered: {consecutive_count} consecutive losses "

                f"in {self.config.loss_streak_settings.time_window_minutes} min window"

            )

            return True, reason

        # Проверка 2: Дневной лимит убытков (если передан equity)

        if equity:

            if not isinstance(equity, Decimal):

                equity = Decimal(str(equity))

            total_loss = sum(loss["loss"] for loss in recent_losses)

            daily_loss_limit = (

                equity * self.config.loss_streak_settings.daily_loss_kill_percent / Decimal("100")

            )

            if total_loss >= daily_loss_limit:

                reason = (

                    f"Daily loss limit triggered: {total_loss:.2f} USD "

                    f">= limit {daily_loss_limit:.2f} USD ({self.config.loss_streak_settings.daily_loss_kill_percent}% of equity)"

                )

                return True, reason

        return False, None

    def check_alert_state(self) -> tuple[bool, Optional[str]]:
        """

        Проверить alert состояние (перед kill switch)


        Returns:

            (should_alert, reason)

        """

        if not self.config.loss_streak_settings or not self.loss_history:

            return False, None

        now = datetime.utcnow()

        window_start = now - timedelta(minutes=self.config.loss_streak_settings.time_window_minutes)

        recent_losses = [loss for loss in self.loss_history if loss["timestamp"] >= window_start]

        # Alert если есть N убытков (но < kill_switch порог)

        consecutive_count = len(recent_losses)

        if consecutive_count >= self.config.loss_streak_settings.alert_on_losses:

            if consecutive_count < self.config.loss_streak_settings.consecutive_losses_threshold:

                reason = f"Loss streak alert: {consecutive_count} consecutive losses (kill switch at {self.config.loss_streak_settings.consecutive_losses_threshold})"

                return True, reason

        return False, None

    def check_spread(self, current_spread_percent: float):
        """Проверка спреда"""

        if current_spread_percent > self.config.loss_streak_settings.max_spread_percent:

            self.trigger_break(

                f"Excessive spread: {current_spread_percent:.2f}% > {self.config.loss_streak_settings.max_spread_percent}%"

            )

    def check_data_freshness(self):
        """Проверка актуальности данных"""

        time_since_last_data = (datetime.now() - self.last_data_timestamp).total_seconds()

        if time_since_last_data > self.config.loss_streak_settings.data_timeout_seconds:

            self.trigger_break(f"Data timeout: no updates for {time_since_last_data:.0f} seconds")

    def update_data_timestamp(self):
        """Обновить временную метку последних данных"""

        self.last_data_timestamp = datetime.now()

    def trigger_volatility_halt(self) -> Dict:
        """Активировать volatility halt"""

        if self.current_state == CircuitState.VOLATILITY_HALT:

            return {"already_halted": True}

        self.current_state = CircuitState.VOLATILITY_HALT

        self.state_timestamp = datetime.utcnow()

        self.recovery_timestamp = self.state_timestamp + timedelta(

            minutes=self.config.volatility_settings.halt_duration_minutes

        )

        event = CircuitBreakerEvent(

            timestamp=self.state_timestamp,

            state=CircuitState.VOLATILITY_HALT,

            reason="Volatility halt triggered",

            details={

                "recovery_at": self.recovery_timestamp.isoformat(),

                "duration_minutes": self.config.volatility_settings.halt_duration_minutes,

            },

        )

        self.events.append(event)

        logger.warning(

            f"CIRCUIT BREAKER: Volatility halt activated for {self.config.volatility_settings.halt_duration_minutes} min"

        )

        return {

            "state": self.current_state.value,

            "recovery_at": self.recovery_timestamp.isoformat(),

        }

    def trigger_kill_switch(self, reason: str = None) -> Dict:
        """

        Активировать kill switch


        Args:

            reason: Причина срабатывания


        Returns:

            Dict с инструкциями для выполнения

        """

        if self.current_state == CircuitState.KILL_SWITCH:

            return {"already_active": True}

        self.current_state = CircuitState.KILL_SWITCH

        self.state_timestamp = datetime.utcnow()

        self.kill_switch_data = {

            "activated_at": self.state_timestamp.isoformat(),

            "reason": reason or "Kill switch triggered",

            "actions_required": [

                "cancel_all_orders",

                "close_all_positions",

                "block_new_orders",

                "alert_user",

            ],

        }

        event = CircuitBreakerEvent(

            timestamp=self.state_timestamp,

            state=CircuitState.KILL_SWITCH,

            reason=reason or "Kill switch triggered",

            details=self.kill_switch_data,

        )

        self.events.append(event)

        logger.critical(f"🚨 KILL SWITCH ACTIVATED: {reason}")

        # Также обновляем legacy поля

        self.is_circuit_broken = True

        self.break_reason = reason

        return self.kill_switch_data

    def trigger_break(self, reason: str):
        """Сработать circuit breaker (legacy)"""

        if not self.is_circuit_broken:

            self.is_circuit_broken = True

            self.break_reason = reason

            logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")

    def check_recovery(self) -> Optional[str]:
        """

        Проверить возможность восстановления из volatility halt


        Returns:

            Reason if can't recover, None if can recover

        """

        if self.current_state != CircuitState.VOLATILITY_HALT:

            return None  # Не в halt

        if not self.recovery_timestamp:

            return "No recovery timestamp set"

        if datetime.utcnow() < self.recovery_timestamp:

            time_left = self.recovery_timestamp - datetime.utcnow()

            return f"Still in halt, {time_left.total_seconds():.0f} sec remaining"

        return None  # Можем восстановиться

    def recover_from_halt(self) -> Dict:
        """Восстановиться из volatility halt"""

        if self.current_state != CircuitState.VOLATILITY_HALT:

            return {"not_in_halt": True}

        if self.check_recovery():

            return {"not_ready": self.check_recovery()}

        self.current_state = CircuitState.ACTIVE

        self.recovery_timestamp = None

        event = CircuitBreakerEvent(

            timestamp=datetime.utcnow(),

            state=CircuitState.ACTIVE,

            reason="Recovered from volatility halt",

            details={},

        )

        self.events.append(event)

        logger.info("CIRCUIT BREAKER: Recovered from volatility halt, resuming trading")

        return {

            "state": self.current_state.value,

            "trading_resumed": True,

        }

    def can_trade(self) -> tuple[bool, Optional[str]]:
        """

        Можно ли торговать сейчас?


        Returns:

            (can_trade, reason_if_not)

        """

        if not self.config.enabled:

            return True, None

        if self.current_state == CircuitState.KILL_SWITCH:

            return False, "Kill switch is active - no trading allowed"

        if self.current_state == CircuitState.VOLATILITY_HALT:

            if self.recovery_timestamp:

                time_left = self.recovery_timestamp - datetime.utcnow()

                if time_left.total_seconds() > 0:

                    return (

                        False,

                        f"Volatility halt active, {time_left.total_seconds():.0f} sec remaining",

                    )

            # Если время истекло, восстановимся

            self.recover_from_halt()

        return True, None

    def get_state(self) -> Dict:
        """Получить текущее состояние"""

        can_trade, reason = self.can_trade()

        return {

            "current_state": self.current_state.value,

            "can_trade": can_trade,

            "block_reason": reason,

            "state_since": self.state_timestamp.isoformat() if self.state_timestamp else None,

            "recovery_at": self.recovery_timestamp.isoformat() if self.recovery_timestamp else None,

            "atr_history_count": len(self.atr_history),

            "loss_history_count": len(self.loss_history),

            "recent_events": [

                {

                    "timestamp": e.timestamp.isoformat(),

                    "state": e.state.value,

                    "reason": e.reason,

                }

                for e in self.events[-5:]  # Последние 5 событий

            ],

        }

    def get_loss_streak_info(self) -> Dict:
        """Получить информацию о убытках"""

        if not self.loss_history:

            return {

                "total_losses": 0,

                "recent_losses": 0,

                "alert_triggered": False,

                "kill_switch_triggered": False,

            }

        now = datetime.utcnow()

        window_start = now - timedelta(minutes=self.config.loss_streak_settings.time_window_minutes)

        recent_losses = [loss for loss in self.loss_history if loss["timestamp"] >= window_start]

        total_recent_loss = sum(loss["loss"] for loss in recent_losses)

        return {

            "total_losses": len(self.loss_history),

            "recent_losses": len(recent_losses),

            "total_loss_amount": float(total_recent_loss),

            "alert_threshold": self.config.loss_streak_settings.alert_on_losses,

            "kill_threshold": self.config.loss_streak_settings.consecutive_losses_threshold,

            "alert_triggered": len(recent_losses)

            >= self.config.loss_streak_settings.alert_on_losses,

            "kill_switch_triggered": self.current_state == CircuitState.KILL_SWITCH,

        }

    def get_volatility_info(self) -> Dict:
        """Получить информацию о волатильности"""

        if not self.atr_history:

            return {

                "atr_readings": 0,

                "current_atr": None,

                "mean_atr": None,

                "volatility_spike": False,

            }

        current_atr = self.atr_history[-1]

        mean_atr = sum(self.atr_history) / len(self.atr_history)

        is_spike, _ = self.check_volatility()

        return {

            "atr_readings": len(self.atr_history),

            "current_atr": float(current_atr),

            "mean_atr": float(mean_atr),

            "atr_ratio": float(current_atr / mean_atr) if mean_atr > 0 else 0,

            "volatility_spike": is_spike,

            "halt_active": self.current_state == CircuitState.VOLATILITY_HALT,

        }

    def reset(self):
        """Сброс circuit breaker (ручной) - LEGACY"""

        logger.info("Circuit breaker reset")

        self.is_circuit_broken = False

        self.break_reason = None

        self.consecutive_losses = 0

    def reset_for_new_day(self) -> None:
        """Сбросить состояние на новый день"""

        # Очистить убытки за день

        self.loss_history.clear()

        # Kill switch требует явного сброса (не сбрасываем автоматически)

        if self.current_state == CircuitState.VOLATILITY_HALT:

            self.recover_from_halt()

        logger.info("CIRCUIT BREAKER: Reset for new day")

    def manual_reset(self) -> Dict:
        """Ручной сброс kill switch (требует подтверждения)"""

        if self.current_state != CircuitState.KILL_SWITCH:

            return {"not_triggered": True}

        self.current_state = CircuitState.ACTIVE

        self.kill_switch_data.clear()

        self.is_circuit_broken = False

        self.break_reason = None

        event = CircuitBreakerEvent(

            timestamp=datetime.utcnow(),

            state=CircuitState.ACTIVE,

            reason="Kill switch manually reset",

            details={},

        )

        self.events.append(event)

        logger.warning("CIRCUIT BREAKER: Kill switch manually reset by user")

        return {

            "state": self.current_state.value,

            "trading_resumed": True,

        }

    def is_trading_allowed(self) -> bool:
        """Разрешена ли торговля? (LEGACY)"""

        can_trade, _ = self.can_trade()

        return can_trade
