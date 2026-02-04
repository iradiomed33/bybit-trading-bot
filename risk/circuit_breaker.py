"""
Circuit Breaker: автоматическая остановка торговли при проблемах.

Триггеры:
- Серия убыточных сделок
- Дневной лимит убытка
- Потеря синхронизации
- Деградация данных (WS отвал)
- Резкий рост спреда
"""

from datetime import datetime
from logger import setup_logger

logger = setup_logger(__name__)


class CircuitBreaker:
    """Автоматический останов торговли"""

    def __init__(
        self,
        max_consecutive_losses: int = 5,
        max_spread_percent: float = 1.0,
        data_timeout_seconds: int = 60,
    ):
        """
        Args:
            max_consecutive_losses: Макс. убыточных сделок подряд
            max_spread_percent: Макс. допустимый спред (%)
            data_timeout_seconds: Таймаут без данных (сек)
        """
        self.max_consecutive_losses = max_consecutive_losses
        self.max_spread_percent = max_spread_percent
        self.data_timeout_seconds = data_timeout_seconds

        # Состояние
        self.is_circuit_broken = False
        self.break_reason = None
        self.consecutive_losses = 0
        self.last_data_timestamp = datetime.now()

        logger.info("CircuitBreaker initialized")

    def check_consecutive_losses(self, last_trade_result: str):
        """
        Проверка серии убыточных сделок.

        Args:
            last_trade_result: 'win' или 'loss'
        """
        if last_trade_result == "loss":
            self.consecutive_losses += 1
            logger.warning(f"Consecutive losses: {self.consecutive_losses}")

            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trigger_break(f"Max consecutive losses reached: {self.consecutive_losses}")
        else:
            # Сбрасываем счётчик при выигрыше
            self.consecutive_losses = 0

    def check_spread(self, current_spread_percent: float):
        """Проверка спреда"""
        if current_spread_percent > self.max_spread_percent:
            self.trigger_break(
                f"Excessive spread: {current_spread_percent:.2f}% > {self.max_spread_percent}%"
            )

    def check_data_freshness(self):
        """Проверка актуальности данных"""
        time_since_last_data = (datetime.now() - self.last_data_timestamp).total_seconds()

        if time_since_last_data > self.data_timeout_seconds:
            self.trigger_break(f"Data timeout: no updates for {time_since_last_data:.0f} seconds")

    def update_data_timestamp(self):
        """Обновить временную метку последних данных"""
        self.last_data_timestamp = datetime.now()

    def trigger_break(self, reason: str):
        """Сработать circuit breaker"""
        if not self.is_circuit_broken:
            self.is_circuit_broken = True
            self.break_reason = reason
            logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")

    def reset(self):
        """Сброс circuit breaker (ручной)"""
        logger.info("Circuit breaker reset")
        self.is_circuit_broken = False
        self.break_reason = None
        self.consecutive_losses = 0

    def is_trading_allowed(self) -> bool:
        """Разрешена ли торговля?"""
        return not self.is_circuit_broken
