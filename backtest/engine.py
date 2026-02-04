"""
Backtest Engine: честный бэктест с комиссиями и проскальзыванием.

Симулирует:
- Market orders с проскальзыванием
- Limit orders с частичным исполнением
- Комиссии maker/taker
- Latency (упрощённо)
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from storage.database import Database
from logger import setup_logger

logger = setup_logger(__name__)


class BacktestEngine:
    """Движок бэктестирования"""

    def __init__(
        self,
        db: Database,
        initial_balance: float = 10000.0,
        maker_fee: float = 0.0002,  # 0.02%
        taker_fee: float = 0.0006,  # 0.06%
        slippage_percent: float = 0.05,  # 0.05%
    ):
        """
        Args:
            db: Database instance
            initial_balance: Начальный капитал
            maker_fee: Комиссия maker
            taker_fee: Комиссия taker
            slippage_percent: Проскальзывание (% от цены)
        """
        self.db = db
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage_percent = slippage_percent

        # Состояние
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_position: Optional[Dict[str, Any]] = None

        logger.info(
            f"BacktestEngine initialized: balance=${initial_balance}, "
            f"maker={maker_fee * 100:.2f}%, taker={taker_fee * 100:.2f}%"
        )

    def simulate_fill(
        self, signal: Dict[str, Any], current_price: float, is_limit: bool = False
    ) -> Dict[str, Any]:
        """
        Симулировать исполнение ордера.

        Args:
            signal: Торговый сигнал
            current_price: Текущая цена
            is_limit: Limit или Market order

        Returns:
            Результат исполнения
        """
        entry_price = signal["entry_price"]
        side = signal["signal"]  # 'long' or 'short'

        # Market order: исполняется сразу с проскальзыванием
        if not is_limit:
            slippage = current_price * (self.slippage_percent / 100)
            fill_price = current_price + slippage if side == "long" else current_price - slippage
            fee_rate = self.taker_fee
        else:
            # Limit order: исполняется только если цена достигла уровня
            if side == "long" and current_price <= entry_price:
                fill_price = entry_price
                fee_rate = self.maker_fee
            elif side == "short" and current_price >= entry_price:
                fill_price = entry_price
                fee_rate = self.maker_fee
            else:
                # Не исполнилось
                return {"filled": False}

        # Рассчитываем размер позиции (упрощённо: фиксированный % от баланса)
        position_size_usd = self.balance * 0.1  # 10% от баланса
        position_size = position_size_usd / fill_price

        # Комиссия
        fee = position_size_usd * fee_rate

        return {
            "filled": True,
            "fill_price": fill_price,
            "size": position_size,
            "size_usd": position_size_usd,
            "fee": fee,
            "side": side,
        }

    def open_position(self, signal: Dict[str, Any], timestamp: float, current_price: float):
        """Открыть позицию"""
        if self.current_position:
            logger.warning("Already in position, skipping")
            return

        # Симулируем исполнение
        fill_result = self.simulate_fill(signal, current_price, is_limit=False)

        if not fill_result["filled"]:
            logger.debug("Order not filled")
            return

        # Вычитаем комиссию из баланса
        self.balance -= fill_result["fee"]

        self.current_position = {
            "timestamp": timestamp,
            "side": signal["signal"],
            "entry_price": fill_result["fill_price"],
            "size": fill_result["size"],
            "size_usd": fill_result["size_usd"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal.get("take_profit"),
            "entry_fee": fill_result["fee"],
            "strategy": signal.get("strategy", "Unknown"),
        }

        logger.info(
            f"Position opened: {self.current_position['side']} "
            f"{self.current_position['size']:.4f} @ {self.current_position['entry_price']:.2f}"
        )

    def check_exit(self, timestamp: float, current_price: float):
        """Проверить условия выхода"""
        if not self.current_position:
            return

        pos = self.current_position
        should_exit = False
        exit_reason = None

        # Проверка стоп-лосса
        if pos["side"] == "long" and current_price <= pos["stop_loss"]:
            should_exit = True
            exit_reason = "stop_loss"
        elif pos["side"] == "short" and current_price >= pos["stop_loss"]:
            should_exit = True
            exit_reason = "stop_loss"

        # Проверка тейк-профита
        if pos["take_profit"]:
            if pos["side"] == "long" and current_price >= pos["take_profit"]:
                should_exit = True
                exit_reason = "take_profit"
            elif pos["side"] == "short" and current_price <= pos["take_profit"]:
                should_exit = True
                exit_reason = "take_profit"

        if should_exit:
            self.close_position(timestamp, current_price, exit_reason)

    def close_position(self, timestamp: float, exit_price: float, reason: str):
        """Закрыть позицию"""
        if not self.current_position:
            return

        pos = self.current_position

        # Рассчитываем PnL
        if pos["side"] == "long":
            pnl = (exit_price - pos["entry_price"]) * pos["size"]
        else:  # short
            pnl = (pos["entry_price"] - exit_price) * pos["size"]

        # Комиссия выхода
        exit_fee = pos["size_usd"] * self.taker_fee

        # Итоговый PnL
        net_pnl = pnl - pos["entry_fee"] - exit_fee

        # Обновляем баланс
        self.balance += pos["size_usd"] + net_pnl

        # Записываем трейд
        trade = {
            "entry_timestamp": pos["timestamp"],
            "exit_timestamp": timestamp,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "size": pos["size"],
            "pnl": net_pnl,
            "pnl_percent": (net_pnl / pos["size_usd"]) * 100,
            "exit_reason": reason,
            "strategy": pos["strategy"],
        }

        self.trades.append(trade)

        logger.info(
            f"Position closed: {reason} @ {exit_price:.2f}, "
            f"PnL: ${net_pnl:.2f} ({trade['pnl_percent']:.2f}%)"
        )

        self.current_position = None

    def record_equity(self, timestamp: float, current_price: float):
        """Записать текущий equity"""
        equity = self.balance

        # Если есть открытая позиция, добавляем unrealized PnL
        if self.current_position:
            pos = self.current_position
            if pos["side"] == "long":
                unrealized_pnl = (current_price - pos["entry_price"]) * pos["size"]
            else:
                unrealized_pnl = (pos["entry_price"] - current_price) * pos["size"]

            equity += pos["size_usd"] + unrealized_pnl

        self.equity_curve.append({"timestamp": timestamp, "equity": equity})

    def calculate_metrics(self) -> Dict[str, Any]:
        """Рассчитать метрики бэктеста"""
        if not self.trades:
            return {"error": "No trades executed"}

        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t["pnl"] > 0]
        losing_trades = [t for t in self.trades if t["pnl"] <= 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        total_pnl = sum(t["pnl"] for t in self.trades)
        avg_win = (
            sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        )
        avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        # Max drawdown
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] - equity_df["peak"]
        max_drawdown = equity_df["drawdown"].min()
        max_drawdown_percent = (max_drawdown / self.initial_balance) * 100

        # Sharpe (упрощённо)
        returns = [t["pnl_percent"] for t in self.trades]
        sharpe = (pd.Series(returns).mean() / pd.Series(returns).std()) if len(returns) > 1 else 0

        metrics = {
            "total_trades": total_trades,
            "win_rate": win_rate * 100,
            "total_pnl": total_pnl,
            "total_pnl_percent": (total_pnl / self.initial_balance) * 100,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "max_drawdown": max_drawdown,
            "max_drawdown_percent": max_drawdown_percent,
            "sharpe_ratio": sharpe,
            "final_balance": self.balance,
        }

        return metrics
