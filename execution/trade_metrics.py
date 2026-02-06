# -*- coding: utf-8 -*-

"""

Trade Metrics Calculator - E1 EPIC


Вычисление метрик для paper trading:

- Equity curve (cash + unrealized PnL через время)

- Profit Factor (gross_profit / gross_loss)

- Max Drawdown (от peak к trough)

- Win Rate (winning_trades / total_trades)

- Expectancy (средний PnL на сделку)

- Sharpe Ratio, Sortino Ratio

- Recovery Factor

"""


from typing import List, Dict, Any, Tuple

from decimal import Decimal

from dataclasses import dataclass

from statistics import mean, stdev

import logging


logger = logging.getLogger(__name__)


@dataclass
class TradeMetrics:

    """Метрики сделок"""

    # Количество сделок

    total_trades: int = 0

    winning_trades: int = 0

    losing_trades: int = 0

    breakeven_trades: int = 0

    # PnL

    gross_profit: Decimal = Decimal("0")

    gross_loss: Decimal = Decimal("0")

    total_pnl: Decimal = Decimal("0")

    avg_pnl_per_trade: Decimal = Decimal("0")

    # Win metrics

    win_rate: Decimal = Decimal("0")  # %

    profit_factor: Decimal = Decimal("0")  # gross_profit / abs(gross_loss)

    expectancy: Decimal = Decimal("0")  # (win_rate * avg_win) - (1 - win_rate) * avg_loss

    # Average metrics

    avg_winning_trade: Decimal = Decimal("0")

    avg_losing_trade: Decimal = Decimal("0")

    largest_winning_trade: Decimal = Decimal("0")

    largest_losing_trade: Decimal = Decimal("0")

    # Duration

    avg_trade_duration_seconds: float = 0.0

    total_trading_duration_seconds: float = 0.0

    # Drawdown

    max_drawdown_percent: Decimal = Decimal("0")

    max_drawdown_dollars: Decimal = Decimal("0")

    # Commission impact

    total_commission_paid: Decimal = Decimal("0")

    commission_as_percent_of_pnl: Decimal = Decimal("0")

    # Risk metrics

    sharpe_ratio: Decimal = Decimal("0")

    sortino_ratio: Decimal = Decimal("0")

    recovery_factor: Decimal = Decimal("0")  # total_pnl / max_drawdown

    # SL/TP stats

    trades_hit_sl: int = 0

    trades_hit_tp: int = 0

    sl_hit_rate: Decimal = Decimal("0")  # %

    tp_hit_rate: Decimal = Decimal("0")  # %


class EquityCurve:

    """Кривая equity через время"""

    def __init__(self):

        self.timestamps = []

        self.equity_values = []

        self.cumulative_pnl = []

        self.max_equity = Decimal("0")

        self.peak_times = []  # Точки где был новый максимум

    def add_point(self, timestamp: float, equity: Decimal):
        """Добавить точку на кривую"""

        self.timestamps.append(timestamp)

        self.equity_values.append(float(equity))

        # Отслеживать peak

        if equity > self.max_equity:

            self.max_equity = equity

            self.peak_times.append(timestamp)

    def __len__(self) -> int:
        """Количество точек на кривой"""

        return len(self.equity_values)

    def __getitem__(self, index: int) -> float:
        """Получить equity значение по индексу"""

        return self.equity_values[index]

    def get_drawdowns(self) -> List[Decimal]:
        """Получить все drawdowns (от peak к trough)"""

        drawdowns = []

        peak = Decimal("0")

        for equity in self.equity_values:

            if equity > peak:

                peak = Decimal(str(equity))

            dd = peak - Decimal(str(equity))

            if dd > 0:

                drawdowns.append(dd)

        return drawdowns

    def get_max_drawdown(self, initial_balance: Decimal) -> Tuple[Decimal, Decimal]:
        """

        Вычислить max drawdown.


        Returns:

            (max_dd_dollars, max_dd_percent)

        """

        if not self.equity_values:

            return Decimal("0"), Decimal("0")

        max_dd = Decimal("0")

        peak = Decimal(str(self.equity_values[0]))

        for equity in self.equity_values:

            equity = Decimal(str(equity))

            if equity > peak:

                peak = equity

            dd = peak - equity

            if dd > max_dd:

                max_dd = dd

        # Вычислить как % от initial balance

        max_dd_percent = (max_dd / initial_balance * 100) if initial_balance > 0 else Decimal("0")

        return max_dd, max_dd_percent

    def get_cagr(self, initial_balance: Decimal, days: float) -> Decimal:
        """

        Вычислить CAGR (Compound Annual Growth Rate).

        """

        if not self.equity_values or days <= 0:

            return Decimal("0")

        final_equity = Decimal(str(self.equity_values[-1]))

        years = days / 365.25

        if years <= 0 or initial_balance <= 0:

            return Decimal("0")

        cagr = (final_equity / initial_balance) ** (1 / years) - 1

        return Decimal(str(cagr)) * 100


class TradeMetricsCalculator:

    """

    Вычислить все метрики из списка Trade объектов.

    """

    @staticmethod
    def calculate(

        trades: List[Any],  # List[Trade]

        initial_balance: Decimal,

        equity_curve: EquityCurve = None,

    ) -> TradeMetrics:
        """

        Вычислить полный набор метрик.


        Args:

            trades: Список Trade объектов

            initial_balance: Начальный баланс

            equity_curve: EquityCurve объект (опционально)


        Returns:

            TradeMetrics с все метрикам

        """

        metrics = TradeMetrics()

        if not trades:

            return metrics

        # Основные счеты

        metrics.total_trades = len(trades)

        pnl_list = []  # Для вычисления статистики

        for trade in trades:

            pnl = trade.pnl_after_commission

            pnl_list.append(float(pnl))

            if pnl > 0:

                metrics.winning_trades += 1

                metrics.gross_profit += pnl

            elif pnl < 0:

                metrics.losing_trades += 1

                metrics.gross_loss += pnl

            else:

                metrics.breakeven_trades += 1

            metrics.total_pnl += pnl

            metrics.total_commission_paid += trade.entry_commission + trade.exit_commission

            # Отслеживать largest wins/losses

            if pnl > metrics.largest_winning_trade:

                metrics.largest_winning_trade = pnl

            if pnl < metrics.largest_losing_trade:

                metrics.largest_losing_trade = pnl

            # SL/TP stats

            if trade.was_sl_hit:

                metrics.trades_hit_sl += 1

            if trade.was_tp_hit:

                metrics.trades_hit_tp += 1

            # Duration

            if hasattr(trade, "duration_seconds") and trade.duration_seconds > 0:

                metrics.total_trading_duration_seconds += trade.duration_seconds

        # Вычислить процентные метрики

        if metrics.total_trades > 0:

            metrics.win_rate = (

                Decimal(metrics.winning_trades) / Decimal(metrics.total_trades)

            ) * 100

            metrics.avg_pnl_per_trade = metrics.total_pnl / Decimal(metrics.total_trades)

            metrics.avg_trade_duration_seconds = (

                metrics.total_trading_duration_seconds / metrics.total_trades

            )

            metrics.sl_hit_rate = (

                Decimal(metrics.trades_hit_sl) / Decimal(metrics.total_trades)

            ) * 100

            metrics.tp_hit_rate = (

                Decimal(metrics.trades_hit_tp) / Decimal(metrics.total_trades)

            ) * 100

        # Profit Factor

        if metrics.gross_loss != 0:

            metrics.profit_factor = abs(metrics.gross_profit / metrics.gross_loss)

        elif metrics.gross_profit > 0:

            metrics.profit_factor = Decimal("inf")

        # Average win/loss

        if metrics.winning_trades > 0:

            metrics.avg_winning_trade = metrics.gross_profit / Decimal(metrics.winning_trades)

        if metrics.losing_trades > 0:

            metrics.avg_losing_trade = metrics.gross_loss / Decimal(metrics.losing_trades)

        # Expectancy

        if metrics.winning_trades > 0 and metrics.losing_trades > 0:

            win_rate = float(metrics.win_rate) / 100

            avg_win = float(metrics.avg_winning_trade)

            avg_loss = abs(float(metrics.avg_losing_trade))

            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

            metrics.expectancy = Decimal(str(expectancy))

        # Commission impact

        if metrics.gross_profit != 0:

            metrics.commission_as_percent_of_pnl = (

                metrics.total_commission_paid / abs(metrics.gross_profit)

            ) * 100

        # Equity curve metrics

        if equity_curve:

            max_dd, max_dd_pct = equity_curve.get_max_drawdown(initial_balance)

            metrics.max_drawdown_dollars = max_dd

            metrics.max_drawdown_percent = max_dd_pct

            # Recovery factor

            if max_dd > 0:

                metrics.recovery_factor = metrics.total_pnl / max_dd

        # Sharpe & Sortino

        if len(pnl_list) > 1:

            metrics.sharpe_ratio = TradeMetricsCalculator._calculate_sharpe(pnl_list)

            metrics.sortino_ratio = TradeMetricsCalculator._calculate_sortino(pnl_list)

        return metrics

    @staticmethod
    def _calculate_sharpe(pnl_list: List[float], risk_free_rate: float = 0.02) -> Decimal:
        """

        Вычислить Sharpe Ratio.


        Sharpe = (mean_return - risk_free_rate) / std_dev

        """

        if len(pnl_list) < 2:

            return Decimal("0")

        try:

            mean_return = mean(pnl_list)

            std_dev = stdev(pnl_list)

            if std_dev == 0:

                return Decimal("0")

            sharpe = (mean_return - risk_free_rate) / std_dev

            return Decimal(str(sharpe))

        except Exception as e:

            logger.error(f"Failed to calculate Sharpe: {e}")

            return Decimal("0")

    @staticmethod
    def _calculate_sortino(pnl_list: List[float], risk_free_rate: float = 0.02) -> Decimal:
        """

        Вычислить Sortino Ratio (используется только downside deviation).


        Sortino = (mean_return - risk_free_rate) / downside_std_dev

        """

        if len(pnl_list) < 2:

            return Decimal("0")

        try:

            mean_return = mean(pnl_list)

            # Downside deviation (только отрицательные отклонения)

            downside_returns = [r - risk_free_rate for r in pnl_list if r < risk_free_rate]

            if not downside_returns:

                return Decimal(str(mean_return / 0.001 if mean_return > 0 else 0))

            # Calculate downside std without numpy

            downside_mean = mean(downside_returns)

            downside_var = sum((r - downside_mean) ** 2 for r in downside_returns) / len(

                downside_returns

            )

            downside_std = downside_var**0.5

            if downside_std == 0:

                return Decimal("0")

            sortino = (mean_return - risk_free_rate) / downside_std

            return Decimal(str(sortino))

        except Exception as e:

            logger.error(f"Failed to calculate Sortino: {e}")

            return Decimal("0")

    @staticmethod
    def format_metrics(metrics: TradeMetrics) -> Dict[str, str]:
        """

        Отформатировать метрики для отображения.


        Returns:

            Dict с красиво отформатированными метриками

        """

        return {

            "Total Trades": str(metrics.total_trades),

            "Winning Trades": f"{metrics.winning_trades} ({float(metrics.win_rate):.1f}%)",

            "Losing Trades": f"{metrics.losing_trades}",

            "Breakeven": f"{metrics.breakeven_trades}",

            "---": "---",

            "Total PnL": f"${float(metrics.total_pnl):.2f}",

            "Gross Profit": f"${float(metrics.gross_profit):.2f}",

            "Gross Loss": f"${float(metrics.gross_loss):.2f}",

            "Profit Factor": (

                f"{float(metrics.profit_factor):.2f}"

                if metrics.profit_factor != Decimal("inf")

                else "∞"

            ),

            "---": "---",

            "Avg PnL/Trade": f"${float(metrics.avg_pnl_per_trade):.2f}",

            "Avg Win": f"${float(metrics.avg_winning_trade):.2f}",

            "Avg Loss": f"${float(metrics.avg_losing_trade):.2f}",

            "Largest Win": f"${float(metrics.largest_winning_trade):.2f}",

            "Largest Loss": f"${float(metrics.largest_losing_trade):.2f}",

            "Expectancy": f"${float(metrics.expectancy):.2f}",

            "---": "---",

            "Max Drawdown": f"${float(metrics.max_drawdown_dollars):.2f} ({float(metrics.max_drawdown_percent):.2f}%)",

            "Recovery Factor": (

                f"{float(metrics.recovery_factor):.2f}" if metrics.recovery_factor > 0 else "N/A"

            ),

            "---": "---",

            "Sharpe Ratio": f"{float(metrics.sharpe_ratio):.2f}",

            "Sortino Ratio": f"{float(metrics.sortino_ratio):.2f}",

            "---": "---",

            "SL Hit Rate": f"{float(metrics.sl_hit_rate):.1f}%",

            "TP Hit Rate": f"{float(metrics.tp_hit_rate):.1f}%",

            "---": "---",

            "Total Commission": f"${float(metrics.total_commission_paid):.2f}",

            "Commission % of Profit": f"{float(metrics.commission_as_percent_of_pnl):.2f}%",

            "Avg Trade Duration": f"{metrics.avg_trade_duration_seconds:.0f}s",

        }
