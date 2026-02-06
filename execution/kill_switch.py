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

import logging


from exchange.base_client import BybitRestClient


logger = logging.getLogger(__name__)


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

    def __init__(self, client: BybitRestClient):
        """

        Initialize Kill Switch Manager.


        Args:

            client: Bybit API client

        """

        self.client = client

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

        # Step 3: Set halted status

        self.is_halted = True

        self.status = KillSwitchStatus.HALTED

        self.halted_at = activation_time

        self.activation_count += 1

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

            symbols: List of symbols (None = all)


        Returns:

            Tuple of (count_cancelled, list_of_errors)

        """

        errors: List[str] = []

        cancelled_count = 0

        try:

            # Get all active orders

            if symbols:

                for symbol in symbols:

                    cancelled, symbol_errors = self._cancel_orders_for_symbol(symbol)

                    cancelled_count += cancelled

                    errors.extend(symbol_errors)

            else:

                # Cancel all symbols - try common trading pairs

                common_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"]

                for symbol in common_symbols:

                    cancelled, symbol_errors = self._cancel_orders_for_symbol(symbol)

                    cancelled_count += cancelled

                    errors.extend(symbol_errors)

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

            # Cancel all pending orders for the symbol

            response = self.client.cancel_all_orders(symbol=symbol)

            if response and "list" in response:

                cancelled_count = len(response["list"])

                for order in response["list"]:

                    self.cancelled_orders.append(

                        {

                            "symbol": symbol,

                            "order_id": order.get("orderId"),

                            "side": order.get("side"),

                            "qty": order.get("qty"),

                            "price": order.get("price"),

                            "cancelled_at": datetime.now().isoformat(),

                        }

                    )

                    logger.warning(

                        f"Cancelled order | Symbol: {symbol} | "

                        f"OrderID: {order.get('orderId')} | "

                        f"Side: {order.get('side')} | "

                        f"Qty: {order.get('qty')}"

                    )

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

            response = self.client.get_positions()

            if response and "list" in response:

                for pos in response["list"]:

                    # Filter by symbols if specified

                    if symbols and pos.get("symbol") not in symbols:

                        continue

                    # Only include open positions

                    if pos.get("size", 0) > 0:

                        positions.append(pos)

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

            # Market order to close position

            response = self.client.place_order(

                symbol=symbol,

                side=close_side,

                order_type="Market",

                qty=float(qty),

                reduce_only=True,  # Only close, don't reverse

                time_in_force="IOC",  # Immediate or Cancel

            )

            if response and response.get("orderId"):

                self.closed_positions.append(

                    {

                        "symbol": symbol,

                        "original_side": current_side,

                        "close_side": close_side,

                        "qty": float(qty),

                        "order_id": response.get("orderId"),

                        "closed_at": datetime.now().isoformat(),

                    }

                )

                logger.warning(

                    f"Closed position | Symbol: {symbol} | "

                    f"Original Side: {current_side} | "

                    f"Qty: {qty} | OrderID: {response.get('orderId')}"

                )

                return True, []

            else:

                error_msg = f"Failed to close position {symbol}: No order ID returned"

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


        Returns:

            True if trading is allowed, False if halted

        """

        return not self.is_halted

    def reset(self) -> None:
        """Reset kill switch to active state (for recovery)."""

        self.is_halted = False

        self.status = KillSwitchStatus.ACTIVE

        self.halted_at = None

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
