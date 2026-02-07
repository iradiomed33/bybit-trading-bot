"""

Kill Switch Manager - Emergency risk management system.


Handles emergency shutdown of all trading activity:

- Cancel all pending orders

- Close all open positions

- Set halted status

- Prevent further trading


Activation scenarios:

1. Manual activation via CLI/API

2. Automatic on critical errors (risk limit breached, connection loss, etc.)

"""


from datetime import datetime

from decimal import Decimal

from enum import Enum

from typing import Dict, List, Optional, Tuple


from exchange.base_client import BybitRestClient

from storage.database import Database

from logger import setup_logger


logger = setup_logger(__name__)


class KillSwitchStatus(Enum):

    """Status of kill switch."""

    ACTIVE = "active"

    HALTED = "halted"

    RECOVERING = "recovering"


class KillSwitchManager:

    """

    Emergency shutdown system for trading bot.


    Responsibilities:

    1. Cancel all pending orders (by symbol or global)

    2. Close all open positions (market/IOC)

    3. Set halted status to prevent further trading

    4. Track activation history and metrics

    5. Provide recovery information

    """

    def __init__(
        self,
        client: BybitRestClient,
        order_manager=None,  # Optional[OrderManager], avoid circular import
        db: Optional[Database] = None,
        allowed_symbols: Optional[List[str]] = None,
    ):
        """

        Initialize Kill Switch Manager.


        Args:

            client: Bybit API client

            order_manager: OrderManager for order/position operations

            db: Database for storing trading_disabled flag

            allowed_symbols: List of allowed trading symbols (optional)

        """

        self.client = client

        self.order_manager = order_manager

        self.db = db

        self.allowed_symbols = allowed_symbols or []

        self.status = KillSwitchStatus.ACTIVE

        self.is_halted = False

        self.halted_at: Optional[datetime] = None

        self.activation_count = 0

        self.activation_history: List[Dict] = []

        self.closed_positions: List[Dict] = []

        self.cancelled_orders: List[Dict] = []

    def activate(

        self,

        reason: str = "Manual activation",

        symbols: Optional[List[str]] = None,

        close_positions: bool = True,

        cancel_orders: bool = True,

    ) -> Dict:
        """

        Activate kill switch - emergency shutdown of all trading.


        Args:

            reason: Reason for activation

            symbols: List of symbols to affect (None = all symbols)

            close_positions: Whether to close positions

            cancel_orders: Whether to cancel orders


        Returns:

            Dict with activation results:

            {

                "success": bool,

                "timestamp": datetime,

                "orders_cancelled": int,

                "positions_closed": int,

                "errors": List[str]

            }

        """

        if self.is_halted:

            logger.warning("Kill switch already halted, skipping activation")

            return {

                "success": False,

                "timestamp": datetime.now(),

                "message": "Already halted",

                "orders_cancelled": 0,

                "positions_closed": 0,

                "errors": ["Already halted"],

            }

        activation_time = datetime.now()

        errors: List[str] = []

        logger.critical(

            f"KILL SWITCH ACTIVATED - Reason: {reason} | "

            f"Time: {activation_time.isoformat()} | "

            f"Symbols: {symbols or 'ALL'}"

        )

        # Step 1: Cancel all pending orders

        cancelled_count = 0

        if cancel_orders:

            cancelled_count, cancel_errors = self._cancel_all_orders(symbols)

            errors.extend(cancel_errors)

        # Step 2: Close all open positions

        closed_count = 0

        if close_positions:

            closed_count, close_errors = self._close_all_positions(symbols)

            errors.extend(close_errors)

        # Step 3: Set halted status and save to database

        self.is_halted = True

        self.status = KillSwitchStatus.HALTED

        self.halted_at = activation_time

        self.activation_count += 1

        # Save trading_disabled flag to database
        if self.db:
            try:
                self.db.save_config("trading_disabled", True)
                logger.warning("Trading disabled flag saved to database")
            except Exception as e:
                error_msg = f"Failed to save trading_disabled flag: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        activation_record = {

            "timestamp": activation_time,

            "reason": reason,

            "symbols": symbols,

            "orders_cancelled": cancelled_count,

            "positions_closed": closed_count,

            "errors": errors,

            "success": len(errors) == 0,

        }

        self.activation_history.append(activation_record)

        logger.critical(

            "Kill switch activated successfully | "

            f"Orders cancelled: {cancelled_count} | "

            f"Positions closed: {closed_count} | "

            f"Errors: {len(errors)}"

        )

        return {

            "success": len(errors) == 0,

            "timestamp": activation_time,

            "orders_cancelled": cancelled_count,

            "positions_closed": closed_count,

            "errors": errors,

        }

    def _cancel_all_orders(self, symbols: Optional[List[str]] = None) -> Tuple[int, List[str]]:
        """

        Cancel all pending orders.


        Args:

            symbols: List of symbols (None = all from allowed_symbols or positions)


        Returns:

            Tuple of (count_cancelled, list_of_errors)

        """

        errors: List[str] = []

        cancelled_count = 0

        try:

            # Determine which symbols to cancel
            symbols_to_cancel = symbols

            if not symbols_to_cancel:
                # Get symbols from open positions
                try:
                    positions = self._get_open_positions()
                    symbols_from_positions = list(set([p.get("symbol") for p in positions if p.get("symbol")]))
                    
                    # Combine with allowed_symbols if available
                    if self.allowed_symbols:
                        symbols_to_cancel = list(set(symbols_from_positions + self.allowed_symbols))
                    else:
                        symbols_to_cancel = symbols_from_positions
                    
                    logger.info(f"Cancelling orders for symbols: {symbols_to_cancel}")
                except Exception as e:
                    logger.warning(f"Failed to get symbols from positions: {e}")
                    # Fallback to allowed_symbols only
                    symbols_to_cancel = self.allowed_symbols if self.allowed_symbols else []

            # Cancel orders for each symbol
            if symbols_to_cancel:
                for symbol in symbols_to_cancel:

                    cancelled, symbol_errors = self._cancel_orders_for_symbol(symbol)

                    cancelled_count += cancelled

                    errors.extend(symbol_errors)
            else:
                logger.warning("No symbols specified for order cancellation")

            logger.warning(f"Cancelled {cancelled_count} orders, errors: {len(errors)}")

        except Exception as e:

            error_msg = f"Failed to cancel orders: {str(e)}"

            logger.error(error_msg)

            errors.append(error_msg)

        return cancelled_count, errors

    def _cancel_orders_for_symbol(self, symbol: str) -> Tuple[int, List[str]]:
        """

        Cancel all orders for specific symbol.


        Args:

            symbol: Trading pair symbol


        Returns:

            Tuple of (count_cancelled, list_of_errors)

        """

        errors: List[str] = []

        cancelled_count = 0

        try:

            # Use OrderManager if available
            if self.order_manager:
                result = self.order_manager.cancel_all_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if result.success:
                    # Parse result to count cancelled orders
                    # Note: cancel_all_orders returns success but doesn't provide exact count
                    # We'll log it as 1 successful cancellation per symbol
                    cancelled_count = 1  # At least one or all orders cancelled
                    
                    self.cancelled_orders.append(
                        {
                            "symbol": symbol,
                            "cancelled_at": datetime.now().isoformat(),
                            "method": "cancel_all_orders",
                        }
                    )
                    
                    logger.warning(
                        f"Cancelled all orders for symbol: {symbol}"
                    )
                else:
                    error_msg = f"Failed to cancel orders for {symbol}: {result.error}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            else:
                error_msg = f"OrderManager not available, cannot cancel orders for {symbol}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:

            error_msg = f"Failed to cancel orders for {symbol}: {str(e)}"

            logger.error(error_msg)

            errors.append(error_msg)

        return cancelled_count, errors

    def _close_all_positions(self, symbols: Optional[List[str]] = None) -> Tuple[int, List[str]]:
        """

        Close all open positions using market orders.


        Args:

            symbols: List of symbols (None = all)


        Returns:

            Tuple of (count_closed, list_of_errors)

        """

        errors: List[str] = []

        closed_count = 0

        try:

            # Get all positions

            positions = self._get_open_positions(symbols)

            for position in positions:

                closed, pos_errors = self._close_position(position)

                if closed:

                    closed_count += 1

                errors.extend(pos_errors)

            logger.warning(f"Closed {closed_count} positions, errors: {len(errors)}")

        except Exception as e:

            error_msg = f"Failed to close positions: {str(e)}"

            logger.error(error_msg)

            errors.append(error_msg)

        return closed_count, errors

    def _get_open_positions(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """

        Get all open positions.


        Args:

            symbols: Filter by symbols (None = all)


        Returns:

            List of open positions

        """

        positions: List[Dict] = []

        try:

            # Use Bybit API v5 to get positions
            response = self.client.post(
                "/v5/position/list",
                params={
                    "category": "linear",
                    "settleCoin": "USDT",
                }
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                position_list = result.get("list", [])

                for pos in position_list:

                    # Filter by symbols if specified

                    if symbols and pos.get("symbol") not in symbols:

                        continue

                    # Only include open positions (size > 0)

                    size = float(pos.get("size", 0))

                    if size > 0:

                        positions.append(pos)
            else:
                logger.error(f"Failed to get positions: {response.get('retMsg', 'Unknown error')}")

        except Exception as e:

            logger.error(f"Failed to get positions: {str(e)}")

        return positions

    def _close_position(self, position: Dict) -> Tuple[bool, List[str]]:
        """

        Close single position with market order.


        Args:

            position: Position dict with symbol, side, size


        Returns:

            Tuple of (success, list_of_errors)

        """

        errors: List[str] = []

        symbol = position.get("symbol")

        current_side = position.get("side")  # Buy or Sell

        qty = Decimal(str(position.get("size", 0)))

        if qty <= 0:

            return False, ["Invalid position size"]

        try:

            # Opposite side to close: if position is long (Buy), sell to close

            close_side = "Sell" if current_side == "Buy" else "Buy"

            # Use OrderManager to create market order
            if self.order_manager:
                result = self.order_manager.create_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    order_type="Market",
                    qty=float(qty),
                    reduce_only=True,  # Important: only reduce position, don't open new one
                    time_in_force="IOC",  # Immediate or Cancel
                )

                if result.success:

                    self.closed_positions.append(

                        {

                            "symbol": symbol,

                            "original_side": current_side,

                            "close_side": close_side,

                            "qty": float(qty),

                            "order_id": result.order_id,

                            "closed_at": datetime.now().isoformat(),

                        }

                    )

                    logger.warning(

                        f"Closed position | Symbol: {symbol} | "

                        f"Original Side: {current_side} | "

                        f"Qty: {qty} | OrderID: {result.order_id}"

                    )

                    return True, []

                else:

                    error_msg = f"Failed to close position {symbol}: {result.error}"

                    logger.error(error_msg)

                    return False, [error_msg]
            else:
                error_msg = f"OrderManager not available, cannot close position {symbol}"
                logger.error(error_msg)
                return False, [error_msg]

        except Exception as e:

            error_msg = f"Exception closing position {symbol}: {str(e)}"

            logger.error(error_msg)

            errors.append(error_msg)

            return False, errors

    def get_status(self) -> Dict:
        """

        Get current kill switch status.


        Returns:

            Status dict with current state and metrics

        """

        return {

            "is_halted": self.is_halted,

            "status": self.status.value,

            "halted_at": self.halted_at.isoformat() if self.halted_at else None,

            "activation_count": self.activation_count,

            "orders_cancelled": len(self.cancelled_orders),

            "positions_closed": len(self.closed_positions),

        }

    def can_trade(self) -> bool:
        """

        Check if trading is allowed.

        Checks both internal state and database flag.


        Returns:

            True if trading is allowed, False if halted

        """

        # Check internal state
        if self.is_halted:
            return False
        
        # Check database flag if available
        if self.db:
            try:
                trading_disabled = self.db.get_config("trading_disabled", False)
                if trading_disabled:
                    return False
            except Exception as e:
                logger.warning(f"Failed to check trading_disabled flag: {e}")
        
        return True

    def reset(self) -> None:
        """Reset kill switch to active state (for recovery)."""

        self.is_halted = False

        self.status = KillSwitchStatus.ACTIVE

        self.halted_at = None

        # Clear trading_disabled flag in database
        if self.db:
            try:
                self.db.save_config("trading_disabled", False)
                logger.info("Trading disabled flag cleared in database")
            except Exception as e:
                logger.error(f"Failed to clear trading_disabled flag: {e}")

        logger.info("Kill switch reset to active state")

    def get_activation_history(self) -> List[Dict]:
        """Get history of all activations."""

        return self.activation_history

    def get_closed_positions(self) -> List[Dict]:
        """Get list of positions closed during activations."""

        return self.closed_positions

    def get_cancelled_orders(self) -> List[Dict]:
        """Get list of orders cancelled during activations."""

        return self.cancelled_orders
