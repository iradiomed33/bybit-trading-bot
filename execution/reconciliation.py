"""
Reconciliation Service for state synchronization with exchange.

Periodically syncs local state (positions, orders, executions) with exchange REST API
to prevent drift and ensure consistency after restarts.
"""

import logging
import threading
import time
from typing import Dict, List, Optional

from execution.position_manager import PositionManager
from storage.database import Database

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Service for reconciling local state with exchange state.
    
    Performs periodic synchronization of:
    - Positions
    - Open orders
    - Recent executions
    """
    
    def __init__(
        self,
        client,
        position_manager: PositionManager,
        db: Database,
        symbol: str,
        reconcile_interval: int = 60,
    ):
        """
        Initialize ReconciliationService.
        
        Args:
            client: BybitRestClient for API calls
            position_manager: PositionManager to update
            db: Database for order/execution tracking
            symbol: Trading symbol
            reconcile_interval: Seconds between reconciliations
        """
        self.client = client
        self.position_manager = position_manager
        self.db = db
        self.symbol = symbol
        self.reconcile_interval = reconcile_interval
        
        self.running = False
        self.reconciliation_thread: Optional[threading.Thread] = None
        
        logger.info(
            f"ReconciliationService initialized for {symbol} "
            f"(interval: {reconcile_interval}s)"
        )
    
    def reconcile_positions(self) -> None:
        """
        Reconcile positions with exchange.
        
        Fetches current positions from exchange and updates local state
        if there's a mismatch.
        """
        try:
            # Fetch positions from exchange
            exchange_positions = self._fetch_positions_from_exchange()
            
            for symbol, exchange_pos in exchange_positions.items():
                local_pos = self.position_manager.positions.get(symbol)
                
                # Check if update needed
                needs_update = False
                if not local_pos:
                    if exchange_pos['size'] != 0:
                        needs_update = True
                        logger.warning(
                            f"Position found on exchange but not locally: "
                            f"{symbol} size={exchange_pos['size']}"
                        )
                else:
                    if (local_pos.size != exchange_pos['size'] or
                        abs(float(local_pos.entry_price) - exchange_pos['avgPrice']) > 0.01):
                        needs_update = True
                        logger.warning(
                            f"Position mismatch for {symbol}: "
                            f"local size={local_pos.size} vs exchange size={exchange_pos['size']}, "
                            f"local entry={local_pos.entry_price} vs exchange entry={exchange_pos['avgPrice']}"
                        )
                
                if needs_update:
                    # Update local position from exchange data
                    self._update_local_position(symbol, exchange_pos)
                    logger.info(f"Position reconciled for {symbol}")
            
            # Check for positions locally that don't exist on exchange
            for symbol, local_pos in self.position_manager.positions.items():
                if symbol not in exchange_positions or exchange_positions[symbol]['size'] == 0:
                    if local_pos.size != 0:
                        logger.warning(
                            f"Position exists locally but not on exchange: {symbol}"
                        )
                        # Close local position
                        self._update_local_position(symbol, {
                            'size': 0,
                            'avgPrice': 0,
                            'side': 'None',
                        })
                        logger.info(f"Closed orphan local position for {symbol}")
        
        except Exception as e:
            logger.error(f"Error reconciling positions: {e}", exc_info=True)
    
    def reconcile_orders(self) -> None:
        """
        Reconcile open orders with exchange.
        
        Updates local DB to match exchange state for open orders.
        """
        try:
            # Fetch open orders from exchange
            exchange_orders = self._fetch_orders_from_exchange()
            exchange_order_ids = {o['orderId'] for o in exchange_orders}
            
            # Get active orders from local DB
            local_orders = self.db.get_active_orders(self.symbol)
            
            # Find orders that are active locally but not on exchange
            for local_order in local_orders:
                order_id = local_order.get('order_id')
                if order_id and order_id not in exchange_order_ids:
                    logger.warning(
                        f"Order {order_id} is active locally but not on exchange, "
                        f"marking as filled/cancelled"
                    )
                    # Update order status in DB
                    self.db.update_order_status(order_id, 'Cancelled')
            
            # Add orders from exchange that aren't in local DB
            for exchange_order in exchange_orders:
                order_id = exchange_order['orderId']
                if not self.db.order_exists(order_id):
                    logger.warning(
                        f"Order {order_id} exists on exchange but not locally, adding"
                    )
                    # Add to DB
                    self.db.save_order({
                        'order_id': order_id,
                        'symbol': exchange_order.get('symbol'),
                        'side': exchange_order.get('side'),
                        'order_type': exchange_order.get('orderType'),
                        'price': exchange_order.get('price', '0'),
                        'qty': exchange_order.get('qty', '0'),
                        'status': exchange_order.get('orderStatus'),
                        'order_link_id': exchange_order.get('orderLinkId'),
                        'created_time': exchange_order.get('createdTime'),
                    })
        
        except Exception as e:
            logger.error(f"Error reconciling orders: {e}", exc_info=True)
    
    def reconcile_executions(self) -> None:
        """
        Reconcile executions with exchange.
        
        Fetches recent executions and adds any missing ones to local DB.
        """
        try:
            # Fetch recent executions from exchange (last 50)
            exchange_execs = self._fetch_executions_from_exchange()
            
            for exec_data in exchange_execs:
                exec_id = exec_data.get('execId')
                if exec_id and not self.db.execution_exists(exec_id):
                    logger.info(f"Adding missed execution: {exec_id}")
                    self.db.save_execution(exec_data)
        
        except Exception as e:
            logger.error(f"Error reconciling executions: {e}", exc_info=True)
    
    def run_reconciliation(self) -> None:
        """
        Run full reconciliation of all states.
        
        This is called on startup and periodically.
        """
        logger.info("Starting reconciliation...")
        
        self.reconcile_positions()
        self.reconcile_orders()
        self.reconcile_executions()
        
        logger.info("Reconciliation complete")
    
    def start_loop(self) -> None:
        """
        Start background reconciliation loop.
        
        Runs reconciliation every reconcile_interval seconds.
        """
        if self.running:
            logger.warning("Reconciliation loop already running")
            return
        
        self.running = True
        self.reconciliation_thread = threading.Thread(
            target=self._reconciliation_loop,
            daemon=True,
            name="ReconciliationLoop",
        )
        self.reconciliation_thread.start()
        logger.info("Reconciliation loop started")
    
    def stop_loop(self) -> None:
        """Stop background reconciliation loop."""
        if not self.running:
            return
        
        logger.info("Stopping reconciliation loop...")
        self.running = False
        
        if self.reconciliation_thread:
            self.reconciliation_thread.join(timeout=5)
        
        logger.info("Reconciliation loop stopped")
    
    def _reconciliation_loop(self) -> None:
        """Background loop for periodic reconciliation."""
        while self.running:
            try:
                time.sleep(self.reconcile_interval)
                if self.running:  # Check again after sleep
                    self.run_reconciliation()
            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}", exc_info=True)
    
    def _fetch_positions_from_exchange(self) -> Dict[str, dict]:
        """
        Fetch positions from exchange REST API.
        
        Returns:
            Dict mapping symbol -> position data
        """
        response = self.client.post(
            "/v5/position/list",
            params={
                "category": "linear",
                "settleCoin": "USDT",
            }
        )
        
        positions = {}
        if response.get("retCode") == 0:
            result = response.get("result", {})
            position_list = result.get("list", [])
            
            for pos in position_list:
                symbol = pos.get("symbol")
                size = float(pos.get("size", 0))
                
                positions[symbol] = {
                    'size': size,
                    'avgPrice': float(pos.get("avgPrice", 0)),
                    'side': pos.get("side", "None"),
                    'positionValue': float(pos.get("positionValue", 0)),
                    'unrealisedPnl': float(pos.get("unrealisedPnl", 0)),
                    'leverage': pos.get("leverage", "1"),
                }
        
        return positions
    
    def _fetch_orders_from_exchange(self) -> List[dict]:
        """
        Fetch open orders from exchange REST API.
        
        Returns:
            List of order dicts
        """
        response = self.client.get(
            "/v5/order/realtime",
            params={
                "category": "linear",
                "symbol": self.symbol,
            }
        )
        
        orders = []
        if response.get("retCode") == 0:
            result = response.get("result", {})
            orders = result.get("list", [])
        
        return orders
    
    def _fetch_executions_from_exchange(self) -> List[dict]:
        """
        Fetch recent executions from exchange REST API.
        
        Returns:
            List of execution dicts
        """
        response = self.client.get(
            "/v5/execution/list",
            params={
                "category": "linear",
                "symbol": self.symbol,
                "limit": 50,
            }
        )
        
        executions = []
        if response.get("retCode") == 0:
            result = response.get("result", {})
            executions = result.get("list", [])
        
        return executions
    
    def _update_local_position(self, symbol: str, exchange_pos: dict) -> None:
        """
        Update local position from exchange data.
        
        Args:
            symbol: Trading symbol
            exchange_pos: Position data from exchange
        """
        size = exchange_pos['size']
        
        if size == 0:
            # Close position
            if symbol in self.position_manager.positions:
                self.position_manager.positions[symbol].size = 0
        else:
            # Update or create position
            from execution.position import Position
            
            position = Position(
                symbol=symbol,
                side=exchange_pos['side'],
                size=size,
                entry_price=exchange_pos['avgPrice'],
            )
            
            self.position_manager.positions[symbol] = position
            
            # Also save to DB
            self.db.save_position({
                'symbol': symbol,
                'side': exchange_pos['side'],
                'size': size,
                'entry_price': exchange_pos['avgPrice'],
                'unrealised_pnl': exchange_pos.get('unrealisedPnl', 0),
            })
