"""
Backtest Gateway - симуляция для бэктестинга.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal

from execution.gateway import IExecutionGateway
from execution.order_result import OrderResult
from logger import setup_logger


logger = setup_logger(__name__)


class BacktestGateway(IExecutionGateway):
    """
    Gateway для backtesting (полная симуляция).
    
    Использует упрощённый симулятор для быстрого бэктестинга.
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        """
        Args:
            initial_balance: Начальный баланс
        """
        self.initial_balance = Decimal(str(initial_balance))
        self.balance = Decimal(str(initial_balance))
        self.positions = {}  # symbol -> position_data
        self.orders = {}  # order_id -> order_data
        self.executions = []  # list of executions
        self.order_id_counter = 0
        logger.info(f"BacktestGateway initialized with balance={initial_balance}")
    
    def _generate_order_id(self) -> str:
        """Генерировать ID ордера."""
        self.order_id_counter += 1
        return f"backtest_{self.order_id_counter}"
    
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
        """Разместить ордер в backtest симуляторе."""
        order_id = self._generate_order_id()
        
        # В backtest режиме Market ордера исполняются мгновенно
        if order_type == "Market":
            # Симулируем исполнение
            exec_price = price if price else 0.0  # В реальности нужна текущая цена
            
            # Обновляем позицию
            if symbol not in self.positions:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "size": 0.0,
                    "entry_price": 0.0,
                    "unrealized_pnl": 0.0,
                }
            
            position = self.positions[symbol]
            current_size = Decimal(str(position["size"]))
            new_qty = Decimal(str(qty))
            
            if side == "Buy":
                position["size"] = float(current_size + new_qty)
            else:  # Sell
                position["size"] = float(current_size - new_qty)
            
            # Если позиция закрылась, удаляем
            if abs(position["size"]) < 0.0001:
                del self.positions[symbol]
            else:
                position["entry_price"] = exec_price
            
            # Сохраняем исполнение
            self.executions.append({
                "exec_id": f"exec_{self.order_id_counter}",
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": exec_price,
                "exec_time": 0,  # В реальности нужен timestamp
            })
            
            logger.debug(f"Backtest order executed: {order_id} {side} {qty} {symbol} @ {exec_price}")
            
            return OrderResult.success_result(
                order_id=order_id,
                raw={"exec_price": exec_price}
            )
        else:
            # Limit ордера сохраняем в pending
            self.orders[order_id] = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "qty": qty,
                "price": price,
                "status": "New",
            }
            
            logger.debug(f"Backtest limit order placed: {order_id}")
            
            return OrderResult.success_result(
                order_id=order_id,
                raw={"status": "New"}
            )
    
    def cancel_order(
        self,
        category: str,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
    ) -> OrderResult:
        """Отменить ордер в backtest."""
        if order_id and order_id in self.orders:
            self.orders[order_id]["status"] = "Cancelled"
            logger.debug(f"Backtest order cancelled: {order_id}")
            return OrderResult.success_result(raw={"cancelled": True})
        
        return OrderResult.error_result(error="Order not found")
    
    def cancel_all_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> OrderResult:
        """Отменить все ордера в backtest."""
        cancelled_count = 0
        for order_id, order in list(self.orders.items()):
            if symbol is None or order["symbol"] == symbol:
                if order["status"] == "New":
                    order["status"] = "Cancelled"
                    cancelled_count += 1
        
        logger.debug(f"Backtest cancelled {cancelled_count} orders")
        return OrderResult.success_result(raw={"cancelled_count": cancelled_count})
    
    def get_position(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить позицию в backtest."""
        return self.positions.get(symbol)
    
    def get_positions(self, category: str) -> List[Dict[str, Any]]:
        """Получить все позиции в backtest."""
        return list(self.positions.values())
    
    def get_open_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получить открытые ордера в backtest."""
        orders = [
            order for order in self.orders.values()
            if order["status"] == "New"
        ]
        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
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
        """Установить SL/TP в backtest (виртуально)."""
        logger.debug(f"Backtest SL/TP set for {symbol}: SL={stop_loss}, TP={take_profit}")
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
        """Отменить SL/TP в backtest."""
        logger.debug(f"Backtest SL/TP cancelled for {symbol}")
        return OrderResult.success_result(raw={"cancelled": True})
    
    def get_account_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Получить баланс в backtest."""
        # Рассчитываем unrealized PnL
        unrealized_pnl = Decimal("0")
        for position in self.positions.values():
            unrealized_pnl += Decimal(str(position.get("unrealized_pnl", 0)))
        
        equity = self.balance + unrealized_pnl
        
        return {
            "balance": float(self.balance),
            "unrealized_pnl": float(unrealized_pnl),
            "equity": float(equity),
        }
    
    def get_executions(
        self,
        category: str,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Получить исполнения в backtest."""
        executions = self.executions
        if symbol:
            executions = [e for e in executions if e["symbol"] == symbol]
        return executions[-limit:] if len(executions) > limit else executions
    
    def update_position_pnl(self, symbol: str, current_price: float):
        """
        Обновить unrealized PnL позиции (вызывается извне при обновлении цены).
        
        Args:
            symbol: Символ
            current_price: Текущая цена
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            entry_price = Decimal(str(position["entry_price"]))
            size = Decimal(str(position["size"]))
            price = Decimal(str(current_price))
            
            if position["side"] == "Buy":
                pnl = (price - entry_price) * size
            else:  # Sell
                pnl = (entry_price - price) * abs(size)
            
            position["unrealized_pnl"] = float(pnl)
