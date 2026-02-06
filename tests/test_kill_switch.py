"""

Tests for Kill Switch Manager - Emergency risk management.


Covers:

1. Activation scenarios (manual, automatic)

2. Order cancellation (all, by symbol)

3. Position closure (market orders, reduceOnly)

4. Status management (halted state)

5. Recovery and history tracking

6. Edge cases (already halted, no positions, etc.)

"""


from datetime import datetime

from unittest.mock import Mock


from execution.kill_switch import KillSwitchManager, KillSwitchStatus


class MockBybitClient:

    """Mock Bybit API client for testing."""

    def __init__(self):

        self.cancel_all_orders_called = False

        self.place_order_called = False

        self.get_positions_called = False

        self.positions = []

        self.orders = []

    def cancel_all_orders(self, symbol):

        self.cancel_all_orders_called = True

        # Return cancelled orders for the symbol

        return {

            "list": [

                {"orderId": f"order_{symbol}_1", "side": "Buy", "qty": "1.0", "price": "50000"},

                {"orderId": f"order_{symbol}_2", "side": "Sell", "qty": "2.0", "price": "51000"},

            ]

        }

    def get_positions(self):

        self.get_positions_called = True

        return {"list": self.positions}

    def place_order(self, symbol, side, order_type, qty, reduce_only, time_in_force):

        self.place_order_called = True

        return {

            "orderId": f"close_{symbol}_{side}",

            "symbol": symbol,

            "side": side,

            "qty": qty,

            "orderType": order_type,

            "timeInForce": time_in_force,

        }


class TestKillSwitchInitialization:

    """Test kill switch initialization."""

    def test_init_creates_active_kill_switch(self):
        """Kill switch should initialize as active."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        assert not ks.is_halted

        assert ks.status == KillSwitchStatus.ACTIVE

        assert ks.halted_at is None

        assert ks.activation_count == 0

    def test_init_empty_history(self):
        """Activation history should start empty."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        assert ks.activation_history == []

        assert ks.closed_positions == []

        assert ks.cancelled_orders == []


class TestManualActivation:

    """Test manual kill switch activation."""

    def test_activate_with_default_reason(self):
        """Activate should use default reason."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        result = ks.activate()

        assert result["success"] is True

        assert ks.is_halted is True

        assert ks.status == KillSwitchStatus.HALTED

    def test_activate_with_custom_reason(self):
        """Activate should accept custom reason."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        reason = "Critical error detected"

        result = ks.activate(reason=reason)

        assert result["success"] is True

        assert ks.activation_history[0]["reason"] == reason

    def test_activate_returns_timestamp(self):
        """Activate result should include timestamp."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        before = datetime.now()

        result = ks.activate()

        after = datetime.now()

        assert "timestamp" in result

        assert before <= result["timestamp"] <= after

    def test_activate_increments_count(self):
        """Each activation should increment counter."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        assert ks.activation_count == 0

        ks.activate()

        assert ks.activation_count == 1

        # Try to activate again - should fail

        result = ks.activate()

        assert result["success"] is False

        assert ks.activation_count == 1  # Should not increment


class TestCancelOrders:

    """Test order cancellation."""

    def test_cancel_all_orders_no_symbol_filter(self):
        """Activate with default should cancel orders."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=True, close_positions=False)

        assert result["success"] is True

        assert result["orders_cancelled"] > 0

        assert client.cancel_all_orders_called

    def test_cancel_all_orders_with_symbol_filter(self):
        """Should cancel orders only for specified symbols."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        symbols = ["BTCUSDT", "ETHUSDT"]

        result = ks.activate(symbols=symbols, cancel_orders=True, close_positions=False)

        assert result["success"] is True

        assert result["orders_cancelled"] > 0

    def test_cancel_orders_tracked_in_history(self):
        """Cancelled orders should be tracked."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=True, close_positions=False)

        assert len(ks.cancelled_orders) > 0

        assert ks.cancelled_orders[0]["symbol"]

        assert ks.cancelled_orders[0]["order_id"]

        assert ks.cancelled_orders[0]["cancelled_at"]

    def test_skip_cancel_when_flag_false(self):
        """Should skip cancellation if cancel_orders=False."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=False)

        assert result["orders_cancelled"] == 0

        assert not client.cancel_all_orders_called


class TestClosePositions:

    """Test position closure."""

    def test_close_position_long(self):
        """Should close long position with Sell order."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"}

        ]

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=True)

        assert result["success"] is True

        assert result["positions_closed"] > 0

        assert client.place_order_called

    def test_close_position_short(self):
        """Should close short position with Buy order."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "ETHUSDT", "side": "Sell", "size": 10.0, "entryPrice": "3000"}

        ]

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=True)

        assert result["success"] is True

        assert result["positions_closed"] > 0

    def test_close_position_market_order(self):
        """Should use market orders to close positions."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"}

        ]

        ks = KillSwitchManager(client)

        # Capture the call to place_order

        original_place_order = client.place_order

        call_args = []

        def capture_place_order(**kwargs):

            call_args.append(kwargs)

            return original_place_order(**kwargs)

        client.place_order = capture_place_order

        ks.activate(cancel_orders=False, close_positions=True)

        # Verify market order parameters

        assert len(call_args) > 0

        assert call_args[0]["order_type"] == "Market"

        assert call_args[0]["reduce_only"] is True

        assert call_args[0]["time_in_force"] == "IOC"

    def test_closed_positions_tracked(self):
        """Closed positions should be tracked."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.5, "entryPrice": "50000"}

        ]

        ks = KillSwitchManager(client)

        ks.activate(cancel_orders=False, close_positions=True)

        assert len(ks.closed_positions) > 0

        assert ks.closed_positions[0]["symbol"] == "BTCUSDT"

        assert ks.closed_positions[0]["original_side"] == "Buy"

        assert ks.closed_positions[0]["close_side"] == "Sell"

        assert ks.closed_positions[0]["qty"] == 1.5

    def test_skip_close_when_flag_false(self):
        """Should skip closure if close_positions=False."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"}

        ]

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=False)

        assert result["positions_closed"] == 0

        assert not client.place_order_called

    def test_close_multiple_positions(self):
        """Should close multiple open positions."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"},

            {"symbol": "ETHUSDT", "side": "Sell", "size": 10.0, "entryPrice": "3000"},

        ]

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=True)

        assert result["positions_closed"] == 2

        assert len(ks.closed_positions) == 2


class TestAlreadyHalted:

    """Test behavior when already halted."""

    def test_cannot_activate_twice(self):
        """Cannot activate kill switch if already halted."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        # First activation

        result1 = ks.activate()

        assert result1["success"] is True

        # Second activation should fail

        result2 = ks.activate()

        assert result2["success"] is False

        assert "Already halted" in result2["message"]

    def test_halted_prevents_trading(self):
        """can_trade() should return False when halted."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        assert ks.can_trade() is True

        ks.activate()

        assert ks.can_trade() is False


class TestStatusManagement:

    """Test status management and reporting."""

    def test_get_status_returns_dict(self):
        """get_status should return complete status dict."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        status = ks.get_status()

        assert isinstance(status, dict)

        assert "is_halted" in status

        assert "status" in status

        assert "halted_at" in status

        assert "activation_count" in status

        assert "orders_cancelled" in status

        assert "positions_closed" in status

    def test_status_before_activation(self):
        """Status should show active before activation."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        status = ks.get_status()

        assert status["is_halted"] is False

        assert status["status"] == "active"

        assert status["halted_at"] is None

        assert status["activation_count"] == 0

    def test_status_after_activation(self):
        """Status should show halted after activation."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate()

        status = ks.get_status()

        assert status["is_halted"] is True

        assert status["status"] == "halted"

        assert status["halted_at"] is not None

        assert status["activation_count"] == 1


class TestRecovery:

    """Test recovery and reset."""

    def test_reset_clears_halted_state(self):
        """reset() should clear halted state."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate()

        assert ks.is_halted is True

        ks.reset()

        assert ks.is_halted is False

        assert ks.status == KillSwitchStatus.ACTIVE

        assert ks.can_trade() is True

    def test_reset_clears_halted_at(self):
        """reset() should clear halted_at timestamp."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate()

        assert ks.halted_at is not None

        ks.reset()

        assert ks.halted_at is None

    def test_can_reactivate_after_reset(self):
        """Should be able to activate after reset."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate()

        assert ks.is_halted is True

        ks.reset()

        assert ks.is_halted is False

        result = ks.activate()

        assert result["success"] is True

        assert ks.is_halted is True


class TestHistory:

    """Test history tracking."""

    def test_activation_history_recorded(self):
        """Each activation should be recorded in history."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate(reason="Manual trigger")

        history = ks.get_activation_history()

        assert len(history) == 1

        assert history[0]["reason"] == "Manual trigger"

        assert history[0]["success"] is True

    def test_activation_history_multiple(self):
        """Should track multiple activations after resets."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate(reason="First trigger")

        ks.reset()

        ks.activate(reason="Second trigger")

        history = ks.get_activation_history()

        assert len(history) == 2

        assert history[0]["reason"] == "First trigger"

        assert history[1]["reason"] == "Second trigger"

    def test_get_closed_positions(self):
        """Should return closed positions from history."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"}

        ]

        ks = KillSwitchManager(client)

        ks.activate()

        closed = ks.get_closed_positions()

        assert len(closed) > 0

        assert closed[0]["symbol"] == "BTCUSDT"

    def test_get_cancelled_orders(self):
        """Should return cancelled orders from history."""

        client = MockBybitClient()

        ks = KillSwitchManager(client)

        ks.activate()

        cancelled = ks.get_cancelled_orders()

        assert len(cancelled) > 0

        assert all("order_id" in order for order in cancelled)


class TestCriticalErrorScenario:

    """Test critical error scenario - the main use case."""

    def test_critical_error_closes_everything(self):
        """When critical error occurs, all positions and orders should close."""

        client = MockBybitClient()

        # Simulate active trading: 2 positions, multiple orders pending

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 2.0, "entryPrice": "50000"},

            {"symbol": "ETHUSDT", "side": "Sell", "size": 15.0, "entryPrice": "3000"},

        ]

        ks = KillSwitchManager(client)

        # Activate kill switch due to critical error

        result = ks.activate(

            reason="Critical error: Equity dropped 20%", cancel_orders=True, close_positions=True

        )

        # Verify response

        assert result["success"] is True

        assert result["orders_cancelled"] > 0

        assert result["positions_closed"] == 2

        assert len(result["errors"]) == 0

        # Verify state

        assert ks.is_halted is True

        assert not ks.can_trade()

        # Verify history

        assert len(ks.closed_positions) == 2

        assert len(ks.cancelled_orders) > 0

    def test_critical_error_with_symbol_filter(self):
        """Critical error on specific symbol should only affect that symbol."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 2.0, "entryPrice": "50000"},

            {"symbol": "ETHUSDT", "side": "Sell", "size": 15.0, "entryPrice": "3000"},

        ]

        ks = KillSwitchManager(client)

        # Only close BTCUSDT

        result = ks.activate(

            reason="Critical error on BTCUSDT",

            symbols=["BTCUSDT"],

            cancel_orders=True,

            close_positions=True,

        )

        # Only BTCUSDT should be closed

        assert result["positions_closed"] <= 1


class TestEdgeCases:

    """Test edge cases and error handling."""

    def test_no_open_positions(self):
        """Should handle no open positions gracefully."""

        client = MockBybitClient()

        client.positions = []

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=True)

        assert result["success"] is True

        assert result["positions_closed"] == 0

    def test_zero_size_position_ignored(self):
        """Should skip positions with zero size."""

        client = MockBybitClient()

        client.positions = [{"symbol": "BTCUSDT", "side": "Buy", "size": 0, "entryPrice": "50000"}]

        ks = KillSwitchManager(client)

        result = ks.activate(cancel_orders=False, close_positions=True)

        assert result["positions_closed"] == 0

    def test_client_exception_handling(self):
        """Should handle API exceptions gracefully."""

        client = Mock()

        client.cancel_all_orders.side_effect = Exception("API Error")

        client.get_positions.side_effect = Exception("API Error")

        ks = KillSwitchManager(client)

        result = ks.activate()

        # Should still set halted state

        assert ks.is_halted is True

        # But indicate errors in result

        assert len(result["errors"]) > 0

    def test_partial_failure_still_halts(self):
        """Should halt even if some operations fail."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 1.0, "entryPrice": "50000"}

        ]

        # Make place_order fail

        client.place_order = Mock(side_effect=Exception("Order failed"))

        ks = KillSwitchManager(client)

        result = ks.activate()

        # Should still be halted

        assert ks.is_halted is True

        # But report errors

        assert len(result["errors"]) > 0


class TestIntegration:

    """Integration tests combining multiple features."""

    def test_full_emergency_shutdown(self):
        """Full emergency shutdown workflow."""

        client = MockBybitClient()

        client.positions = [

            {"symbol": "BTCUSDT", "side": "Buy", "size": 5.0, "entryPrice": "50000"},

            {"symbol": "ETHUSDT", "side": "Sell", "size": 25.0, "entryPrice": "3000"},

        ]

        ks = KillSwitchManager(client)

        # Verify initial state

        assert ks.can_trade() is True

        # Trigger emergency shutdown

        result = ks.activate(

            reason="Liquidation risk detected", cancel_orders=True, close_positions=True

        )

        # Verify result

        assert result["success"] is True

        assert result["orders_cancelled"] > 0

        assert result["positions_closed"] == 2

        # Verify state changes

        assert not ks.can_trade()

        # Check status

        status = ks.get_status()

        assert status["is_halted"] is True

        assert status["activation_count"] == 1

        # Try to activate again - should fail

        result2 = ks.activate()

        assert result2["success"] is False

        # Recovery process

        ks.reset()

        assert ks.can_trade() is True

        # Can activate again after reset

        result3 = ks.activate()

        assert result3["success"] is True

        assert ks.activation_count == 2
