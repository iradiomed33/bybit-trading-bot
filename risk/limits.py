"""
Risk Limits: проверка лимитов перед каждой сделкой.

Лимиты:
- Max daily loss
- Max drawdown
- Max trades per day
- Max concurrent positions
- Max exposure per symbol
"""

from typing import Dict, Any
from storage.database import Database
from logger import setup_logger

logger = setup_logger(__name__)


class RiskLimits:
    """Управление лимитами риска"""

    def __init__(
        self,
        db: Database,
        max_daily_loss_percent: float = 5.0,
        max_drawdown_percent: float = 10.0,
        max_trades_per_day: int = 20,
        max_concurrent_positions: int = 3,
        max_exposure_per_symbol_percent: float = 30.0,
    ):
        """
        Args:
            db: Database instance
            max_daily_loss_percent: Максимальный дневной убыток (%)
            max_drawdown_percent: Максимальная просадка (%)
            max_trades_per_day: Макс. сделок в день
            max_concurrent_positions: Макс. одновременных позиций
            max_exposure_per_symbol_percent: Макс. экспозиция на 1 символ (%)
        """
        self.db = db
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_drawdown_percent = max_drawdown_percent
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions
        self.max_exposure_per_symbol_percent = max_exposure_per_symbol_percent

        # Внутренние счётчики
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.current_positions = []

        logger.info("RiskLimits initialized")

    def check_limits(
        self, account_balance: float, proposed_trade: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Проверить все лимиты перед открытием позиции.

        Args:
            account_balance: Текущий баланс
            proposed_trade: Предлагаемая сделка (symbol, size, value)

        Returns:
            Dict с результатом проверки
        """
        violations = []

        # 1. Проверка дневного убытка
        if self.daily_pnl < 0:
            daily_loss_percent = abs(self.daily_pnl / account_balance) * 100
            if daily_loss_percent > self.max_daily_loss_percent:
                violations.append(
                    f"Daily loss limit exceeded: {daily_loss_percent:.2f}% > "
                    f"{self.max_daily_loss_percent}%"
                )

        # 2. Проверка количества сделок
        if self.trades_today >= self.max_trades_per_day:
            violations.append(
                f"Max trades per day exceeded: {self.trades_today} >= {self.max_trades_per_day}"
            )

        # 3. Проверка одновременных позиций
        if len(self.current_positions) >= self.max_concurrent_positions:
            violations.append(
                f"Max concurrent positions exceeded: "
                f"{len(self.current_positions)} >= {self.max_concurrent_positions}"
            )

        # 4. Проверка экспозиции на символ
        symbol = proposed_trade.get("symbol")
        proposed_value = proposed_trade.get("value", 0)
        total_exposure = proposed_value

        # Суммируем существующую экспозицию по этому символу
        for pos in self.current_positions:
            if pos.get("symbol") == symbol:
                total_exposure += pos.get("value", 0)

        exposure_percent = (total_exposure / account_balance) * 100
        if exposure_percent > self.max_exposure_per_symbol_percent:
            violations.append(
                f"Max exposure per symbol exceeded: {exposure_percent:.2f}% > "
                f"{self.max_exposure_per_symbol_percent}%"
            )

        # Результат
        if violations:
            logger.warning(f"Risk limits violated: {violations}")
            return {"allowed": False, "violations": violations}
        else:
            logger.debug("Risk limits check passed")
            return {"allowed": True, "violations": []}

    def update_daily_stats(self, pnl: float):
        """Обновить дневную статистику PnL"""
        self.daily_pnl += pnl
        logger.debug(f"Daily PnL updated: {self.daily_pnl:.2f}")

    def increment_trade_count(self):
        """Увеличить счётчик сделок"""
        self.trades_today += 1
        logger.debug(f"Trade count: {self.trades_today}/{self.max_trades_per_day}")

    def add_position(self, position: Dict[str, Any]):
        """Добавить позицию в список активных"""
        self.current_positions.append(position)
        logger.debug(f"Position added: {position.get('symbol')}")

    def remove_position(self, symbol: str):
        """Удалить позицию из списка активных"""
        self.current_positions = [p for p in self.current_positions if p.get("symbol") != symbol]
        logger.debug(f"Position removed: {symbol}")

    def reset_daily_stats(self):
        """Сброс дневной статистики (вызывается в начале нового дня)"""
        logger.info("Resetting daily stats")
        self.daily_pnl = 0.0
        self.trades_today = 0
