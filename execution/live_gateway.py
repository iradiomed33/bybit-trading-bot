"""
Bybit Live Gateway - реальная торговля на Bybit.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal

from execution.gateway import IExecutionGateway
from execution.order_result import OrderResult
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from logger import setup_logger


logger = setup_logger(__name__)


class BybitLiveGateway(IExecutionGateway):
    """
    Gateway для реальной торговли на Bybit.
    
    Использует OrderManager и PositionManager для выполнения операций.
    """
    
    def __init__(
        self,
        order_manager: OrderManager,
        position_manager: PositionManager,
    ):
        """
        Args:
            order_manager: Менеджер ордеров
            position_manager: Менеджер позиций
        """
        self.order_manager = order_manager
        self.position_manager = position_manager
        logger.info("BybitLiveGateway initialized")
    
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
        """Разместить ордер через OrderManager."""
        return self.order_manager.create_order(
            category=category,
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            time_in_force=time_in_force,
            order_link_id=order_link_id,
            **kwargs
        )
    
    def cancel_order(
        self,
        category: str,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
    ) -> OrderResult:
        """Отменить ордер через OrderManager."""
        return self.order_manager.cancel_order(
            category=category,
            symbol=symbol,
            order_id=order_id,
            order_link_id=order_link_id,
        )
    
    def cancel_all_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> OrderResult:
        """Отменить все ордера через OrderManager."""
        return self.order_manager.cancel_all_orders(
            category=category,
            symbol=symbol,
        )
    
    def get_position(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить позицию через PositionManager."""
        position = self.position_manager.get_position(symbol)
        if position:
            return {
                "symbol": symbol,
                "side": position.side,
                "size": float(position.size),
                "entry_price": float(position.entry_price),
                "unrealized_pnl": float(position.unrealised_pnl) if hasattr(position, 'unrealised_pnl') else 0.0,
            }
        return None
    
    def get_positions(self, category: str) -> List[Dict[str, Any]]:
        """Получить все позиции через PositionManager."""
        positions = []
        for symbol, position in self.position_manager.positions.items():
            positions.append({
                "symbol": symbol,
                "side": position.side,
                "size": float(position.size),
                "entry_price": float(position.entry_price),
                "unrealized_pnl": float(position.unrealised_pnl) if hasattr(position, 'unrealised_pnl') else 0.0,
            })
        return positions
    
    def get_open_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получить открытые ордера через OrderManager."""
        # OrderManager использует AccountClient для получения ордеров
        # Вызываем через client напрямую
        response = self.order_manager.client.post(
            "/v5/order/realtime",
            params={
                "category": category,
                "symbol": symbol,
            }
        )
        
        if response.get("retCode") == 0:
            return response.get("result", {}).get("list", [])
        return []
    
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
        """Установить SL/TP через OrderManager."""
        return self.order_manager.set_trading_stop(
            category=category,
            symbol=symbol,
            stop_loss=stop_loss,
            take_profit=take_profit,
            sl_trigger_by=sl_trigger_by,
            tp_trigger_by=tp_trigger_by,
            **kwargs
        )
    
    def cancel_trading_stop(
        self,
        category: str,
        symbol: str,
    ) -> OrderResult:
        """Отменить SL/TP через OrderManager."""
        return self.order_manager.cancel_trading_stop(
            category=category,
            symbol=symbol,
        )
    
    def get_account_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Получить баланс через OrderManager client."""
        response = self.order_manager.client.post(
            "/v5/account/wallet-balance",
            params={"accountType": account_type}
        )
        
        if response.get("retCode") == 0:
            return response.get("result", {})
        return {}
    
    def get_executions(
        self,
        category: str,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Получить исполнения через OrderManager client."""
        params = {
            "category": category,
            "limit": limit,
        }
        if symbol:
            params["symbol"] = symbol
        
        response = self.order_manager.client.post(
            "/v5/execution/list",
            params=params
        )
        
        if response.get("retCode") == 0:
            return response.get("result", {}).get("list", [])
        return []
