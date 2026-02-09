"""
Paper Trading Gateway - симуляция с реальными ценами.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal

from execution.gateway import IExecutionGateway
from execution.order_result import OrderResult
from execution.paper_trading_simulator import PaperTradingSimulator
from logger import setup_logger


logger = setup_logger(__name__)


class PaperGateway(IExecutionGateway):
    """
    Gateway для paper trading (симуляция с реальными ценами).
    
    Использует PaperTradingSimulator для эмуляции торговли.
    """
    
    def __init__(self, paper_simulator: PaperTradingSimulator):
        """
        Args:
            paper_simulator: Симулятор paper trading
        """
        self.simulator = paper_simulator
        logger.info("PaperGateway initialized")
    
    def place_order(
        self,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        order_link_id: Optional[str] = None,
        **kwargs
    ) -> OrderResult:
        """Разместить ордер в симуляторе."""
        # PaperTradingSimulator использует другую сигнатуру
        # Адаптируем вызов
        result_dict = self.simulator.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
        )
        
        # Конвертируем dict в OrderResult
        if result_dict.get("success"):
            return OrderResult.success_result(
                order_id=result_dict.get("order_id"),
                raw=result_dict
            )
        else:
            return OrderResult.error_result(
                error=result_dict.get("error", "Unknown error"),
                raw=result_dict
            )
    
    def cancel_order(
        self,
        category: str,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
    ) -> OrderResult:
        """Отменить ордер в симуляторе."""
        result_dict = self.simulator.cancel_order(order_id=order_id)
        
        if result_dict.get("success"):
            return OrderResult.success_result(raw=result_dict)
        else:
            return OrderResult.error_result(
                error=result_dict.get("error", "Unknown error"),
                raw=result_dict
            )
    
    def cancel_all_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> OrderResult:
        """Отменить все ордера в симуляторе."""
        # PaperTradingSimulator может не иметь этого метода
        # Получаем все ордера и отменяем по одному
        open_orders = self.simulator.get_open_orders()
        cancelled_count = 0
        
        for order in open_orders:
            if symbol is None or order.get("symbol") == symbol:
                result = self.simulator.cancel_order(order_id=order.get("order_id"))
                if result.get("success"):
                    cancelled_count += 1
        
        return OrderResult.success_result(
            raw={"cancelled_count": cancelled_count}
        )
    
    def get_position(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить позицию из симулятора."""
        position = self.simulator.get_position(symbol)
        if position:
            return {
                "symbol": symbol,
                "side": position.get("side"),
                "size": position.get("size", 0.0),
                "entry_price": position.get("entry_price", 0.0),
                "unrealized_pnl": position.get("unrealized_pnl", 0.0),
            }
        return None
    
    def get_positions(self, category: str) -> List[Dict[str, Any]]:
        """Получить все позиции из симулятора."""
        # PaperTradingSimulator хранит позиции по символам
        positions = []
        if hasattr(self.simulator, 'positions'):
            for symbol, position in self.simulator.positions.items():
                positions.append({
                    "symbol": symbol,
                    "side": position.get("side"),
                    "size": position.get("size", 0.0),
                    "entry_price": position.get("entry_price", 0.0),
                    "unrealized_pnl": position.get("unrealized_pnl", 0.0),
                })
        return positions
    
    def get_open_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получить открытые ордера из симулятора."""
        orders = self.simulator.get_open_orders()
        if symbol:
            orders = [o for o in orders if o.get("symbol") == symbol]
        return orders
    
    def set_trading_stop(
        self,
        category: str,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        sl_trigger_by: str = "LastPrice",
        tp_trigger_by: str = "LastPrice",
        **kwargs
    ) -> OrderResult:
        """Установить SL/TP в симуляторе."""
        # PaperTradingSimulator может не поддерживать SL/TP напрямую
        # Возвращаем успешный результат (в симуляторе SL/TP управляются виртуально)
        logger.info(f"Setting SL/TP for {symbol}: SL={stop_loss}, TP={take_profit}")
        return OrderResult.success_result(
            raw={
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "mode": "virtual"
            }
        )
    
    def cancel_trading_stop(
        self,
        category: str,
        symbol: str,
    ) -> OrderResult:
        """Отменить SL/TP в симуляторе."""
        logger.info(f"Cancelling SL/TP for {symbol}")
        return OrderResult.success_result(raw={"cancelled": True})
    
    def get_account_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Получить баланс из симулятора."""
        if hasattr(self.simulator, 'balance'):
            return {
                "balance": float(self.simulator.balance),
                "equity": float(self.simulator.balance),  # В paper mode equity = balance
            }
        return {"balance": 0.0, "equity": 0.0}
    
    def get_executions(
        self,
        category: str,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Получить исполнения из симулятора."""
        if hasattr(self.simulator, 'executions'):
            executions = list(self.simulator.executions)
            if symbol:
                executions = [e for e in executions if e.get("symbol") == symbol]
            return executions[-limit:] if len(executions) > limit else executions
        return []
