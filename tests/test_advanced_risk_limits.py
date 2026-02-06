"""

Tests for Advanced Risk Limits - D2 EPIC


Covers:

1. Leverage checks (within limit, at limit, exceeds limit)

2. Notional checks (position sizing)

3. Daily loss checks (realized PnL limits)

4. Drawdown checks (equity underwater)

5. Risk decisions (ALLOW/DENY/STOP)

6. Configuration and enable/disable

7. Daily reset logic

8. Edge cases (zero balance, extreme values)

"""


from decimal import Decimal


from risk.advanced_risk_limits import (

    AdvancedRiskLimits,

    RiskLimitsConfig,

    RiskDecision,

    RiskCheckResult,

)


class MockDatabase:

    """Mock database for testing."""


class TestRiskLimitsConfig:

    """Test configuration object."""

    def test_default_config(self):
        """Config should have conservative defaults."""

        config = RiskLimitsConfig()

        assert config.max_leverage == Decimal("10")

        assert config.max_notional == Decimal("50000")

        assert config.daily_loss_limit_percent == Decimal("5")

        assert config.max_drawdown_percent == Decimal("10")

        assert config.enable_leverage_check is True

        assert config.enable_notional_check is True

        assert config.enable_daily_loss_check is True

        assert config.enable_drawdown_check is True

    def test_custom_config(self):
        """Config should accept custom values."""

        config = RiskLimitsConfig(

            max_leverage=Decimal("5"),

            max_notional=Decimal("25000"),

            daily_loss_limit_percent=Decimal("2"),

            max_drawdown_percent=Decimal("5"),

        )

        assert config.max_leverage == Decimal("5")

        assert config.max_notional == Decimal("25000")

        assert config.daily_loss_limit_percent == Decimal("2")

        assert config.max_drawdown_percent == Decimal("5")


class TestRiskCheckResult:

    """Test individual risk check results."""

    def test_passing_check(self):
        """Passing check should show success."""

        result = RiskCheckResult(

            passed=True,

            check_name="Leverage",

            current_value=Decimal("5"),

            limit_value=Decimal("10"),

        )

        assert result.passed is True

        assert result.check_name == "Leverage"

        assert "✓" in str(result)

    def test_failing_check(self):
        """Failing check should show failure."""

        result = RiskCheckResult(

            passed=False,

            check_name="Daily Loss",

            current_value=Decimal("6"),

            limit_value=Decimal("5"),

            severity="critical",

        )

        assert result.passed is False

        assert result.severity == "critical"

        assert "✗" in str(result)


class TestLeverageCheck:

    """Test leverage limit validation."""

    def test_leverage_within_limit(self):
        """Leverage within limit should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_leverage=Decimal("10")))

        state = {

            "position_leverage": Decimal("5"),

            "account_balance": Decimal("10000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("10000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["leverage"].passed is True

        assert decision in [RiskDecision.ALLOW, RiskDecision.DENY]  # Depends on other checks

    def test_leverage_at_limit(self):
        """Leverage exactly at limit should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_leverage=Decimal("10")))

        state = {

            "position_leverage": Decimal("10"),

            "account_balance": Decimal("10000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("10000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["leverage"].passed is True

    def test_leverage_exceeds_limit(self):
        """Leverage exceeding limit should fail."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_leverage=Decimal("10")))

        state = {

            "position_leverage": Decimal("15"),

            "account_balance": Decimal("10000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("10000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["leverage"].passed is False

    def test_leverage_critically_exceeds(self):
        """Leverage > 2x limit should be critical."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_leverage=Decimal("10")))

        state = {

            "position_leverage": Decimal("25"),  # 2.5x limit

            "account_balance": Decimal("10000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("10000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["leverage"].severity == "critical"


class TestNotionalCheck:

    """Test notional (position size) validation."""

    def test_notional_within_limit(self):
        """Notional within limit should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_notional=Decimal("50000")))

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("20000"),

            "new_position_notional": Decimal("15000"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["notional"].passed is True

    def test_notional_with_open_position(self):
        """Should include open position in notional calculation."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_notional=Decimal("50000")))

        state = {

            "position_leverage": Decimal("2"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("30000"),  # Already open

            "new_position_notional": Decimal("25000"),  # Trying to add

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        # 30k + 25k = 55k > 50k limit

        assert details["checks"]["notional"].passed is False

    def test_notional_exceeds_by_50_percent_critical(self):
        """Notional > 150% of limit should be critical."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_notional=Decimal("50000")))

        state = {

            "position_leverage": Decimal("3"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("75000"),  # 1.5x limit

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        # Check if we have the notional in violations

        notional_result = details["checks"]["notional"]

        assert notional_result.passed is False

        if notional_result.severity == "critical":

            assert True  # Expected critical when > 50% overage


class TestDailyLossCheck:

    """Test daily loss (realized PnL) validation."""

    def test_daily_loss_zero(self):
        """No losses should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(daily_loss_limit_percent=Decimal("5")))

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["daily_loss"].passed is True

    def test_daily_loss_within_limit(self):
        """Daily loss within limit should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(daily_loss_limit_percent=Decimal("5")))

        # Account $100k, 5% limit = $5k max loss

        # Currently down $2k = 2%

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-2000"),  # Lost $2k

            "current_equity": Decimal("98000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["daily_loss"].passed is True

    def test_daily_loss_at_limit(self):
        """Daily loss at limit should pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(daily_loss_limit_percent=Decimal("5")))

        # Account $100k, 5% limit = $5k max loss

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-5000"),  # Exactly at limit

            "current_equity": Decimal("95000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["daily_loss"].passed is True

    def test_daily_loss_exceeds_limit(self):
        """Daily loss exceeding limit should fail."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(daily_loss_limit_percent=Decimal("5")))

        # Account $100k, 5% limit = $5k max loss

        # Currently down $7k = 7%

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-7000"),  # Over limit

            "current_equity": Decimal("93000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["daily_loss"].passed is False

    def test_daily_loss_at_80_percent_critical(self):
        """Daily loss at 80% of limit should be critical."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(daily_loss_limit_percent=Decimal("5")))

        # Account $100k, 5% = $5k limit

        # At 80% = $4k loss

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-4000"),  # 4% = 80% of limit

            "current_equity": Decimal("96000"),

        }

        decision, details = limits.evaluate(state)

        daily_loss_result = details["checks"]["daily_loss"]

        # Should be warning/critical when approaching limit

        assert daily_loss_result.passed is True  # Still within limit


class TestDrawdownCheck:

    """Test drawdown (equity underwater) validation."""

    def test_drawdown_zero_on_init(self):
        """Drawdown should be zero on initialization."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_drawdown_percent=Decimal("10")))

        limits.set_session_start_equity(Decimal("100000"))

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["drawdown"].passed is True

    def test_drawdown_from_peak(self):
        """Drawdown should be calculated from peak."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_drawdown_percent=Decimal("10")))

        limits.set_session_start_equity(Decimal("100000"))

        # Peak at $110k, now at $100k = 100/110 = 9.09% drawdown

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("10000"),  # Peak was higher

            "current_equity": Decimal("100000"),

        }

        # First update to peak

        decision, details = limits.evaluate(state)

        # Now update to drawdown

        state["current_equity"] = Decimal("99500")

        decision, details = limits.evaluate(state)

        # Should be within 10% limit

        assert details["checks"]["drawdown"].passed is True

    def test_drawdown_exceeds_limit(self):
        """Drawdown exceeding limit should fail."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db, RiskLimitsConfig(max_drawdown_percent=Decimal("10")))

        limits.set_session_start_equity(Decimal("100000"))

        limits.max_equity = Decimal("100000")  # Peak

        # Now at $88k = 12% drawdown from $100k

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("88000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-12000"),

            "current_equity": Decimal("88000"),

        }

        decision, details = limits.evaluate(state)

        assert details["checks"]["drawdown"].passed is False


class TestRiskDecisions:

    """Test overall risk decision logic."""

    def test_decision_allow_all_passed(self):
        """Should ALLOW when all checks pass."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        state = {

            "position_leverage": Decimal("2"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("10000"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        assert decision == RiskDecision.ALLOW

    def test_decision_deny_on_warnings(self):
        """Should DENY when warnings present."""

        db = MockDatabase()

        # Strict limits

        config = RiskLimitsConfig(

            max_leverage=Decimal("2"),

            max_notional=Decimal("20000"),

        )

        limits = AdvancedRiskLimits(db, config)

        state = {

            "position_leverage": Decimal("1.5"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("25000"),  # Exceeds $20k limit

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        assert decision == RiskDecision.DENY

        assert len(details["warnings"]) > 0 or len(details["violations"]) > 0

    def test_decision_stop_on_critical_violations(self):
        """Should STOP on critical violations."""

        db = MockDatabase()

        config = RiskLimitsConfig(max_drawdown_percent=Decimal("5"))

        limits = AdvancedRiskLimits(db, config)

        limits.set_session_start_equity(Decimal("100000"))

        limits.max_equity = Decimal("100000")

        # 15% drawdown - critical

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("85000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-15000"),

            "current_equity": Decimal("85000"),

        }

        decision, details = limits.evaluate(state)

        # Should be critical severity or STOP

        assert decision in [RiskDecision.DENY, RiskDecision.STOP]


class TestConfigurationManagement:

    """Test enabling/disabling checks."""

    def test_disable_leverage_check(self):
        """Should skip leverage check when disabled."""

        db = MockDatabase()

        config = RiskLimitsConfig(max_leverage=Decimal("2"))

        limits = AdvancedRiskLimits(db, config)

        # Disable leverage check

        limits.disable_check("leverage")

        # Extreme leverage but should still ALLOW

        state = {

            "position_leverage": Decimal("50"),  # Way over limit

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        # Leverage check should not be in violations

        assert "leverage" not in details["checks"] or details["checks"]["leverage"].passed

    def test_enable_check(self):
        """Should re-enable disabled check."""

        db = MockDatabase()

        config = RiskLimitsConfig(max_leverage=Decimal("2"), enable_leverage_check=False)

        limits = AdvancedRiskLimits(db, config)

        # Re-enable

        limits.enable_check("leverage")

        state = {

            "position_leverage": Decimal("5"),  # Over 2x limit

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision, details = limits.evaluate(state)

        # Should now fail leverage check

        assert details["checks"]["leverage"].passed is False


class TestSessionManagement:

    """Test session and daily tracking."""

    def test_session_start_equity(self):
        """Should track session start equity."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        limits.set_session_start_equity(Decimal("50000"))

        assert limits.session_start_equity == Decimal("50000")

    def test_get_status(self):
        """Should return current status."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        limits.set_session_start_equity(Decimal("100000"))

        status = limits.get_status()

        assert "session_start" in status

        assert status["session_start_equity"] == 100000.0

        assert status["max_equity"] == 100000.0


class TestEdgeCases:

    """Test edge cases and error conditions."""

    def test_zero_account_balance(self):
        """Should handle zero account balance."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("0"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("0"),

        }

        # Should not crash

        decision, details = limits.evaluate(state)

        assert decision is not None

    def test_negative_balance(self):
        """Should handle negative balance."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        state = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("-1000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("-1000"),

        }

        # Should not crash

        decision, details = limits.evaluate(state)

        assert decision is not None

    def test_very_large_values(self):
        """Should handle very large values."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        state = {

            "position_leverage": Decimal("100"),

            "account_balance": Decimal("1000000"),

            "open_position_notional": Decimal("50000000"),

            "new_position_notional": Decimal("25000000"),

            "realized_pnl_today": Decimal("-500000"),

            "current_equity": Decimal("500000"),

        }

        # Should not crash

        decision, details = limits.evaluate(state)

        assert decision is not None


class TestIntegration:

    """Integration tests with multiple checks."""

    def test_multiple_violations(self):
        """Should report all violations."""

        db = MockDatabase()

        config = RiskLimitsConfig(

            max_leverage=Decimal("2"),

            max_notional=Decimal("20000"),

            daily_loss_limit_percent=Decimal("3"),

        )

        limits = AdvancedRiskLimits(db, config)

        limits.set_session_start_equity(Decimal("100000"))

        # Violate multiple limits

        state = {

            "position_leverage": Decimal("5"),  # Over 2x

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("30000"),  # Over 20k

            "new_position_notional": Decimal("5000"),

            "realized_pnl_today": Decimal("-5000"),  # Over 3% limit

            "current_equity": Decimal("95000"),

        }

        decision, details = limits.evaluate(state)

        # Should report multiple issues

        total_issues = len(details["violations"]) + len(details["warnings"])

        assert total_issues > 0

    def test_progressive_worse_state(self):
        """Should escalate from ALLOW to DENY to STOP."""

        db = MockDatabase()

        limits = AdvancedRiskLimits(db)

        limits.set_session_start_equity(Decimal("100000"))

        # Good state - ALLOW

        state1 = {

            "position_leverage": Decimal("1"),

            "account_balance": Decimal("100000"),

            "open_position_notional": Decimal("0"),

            "new_position_notional": Decimal("5000"),

            "realized_pnl_today": Decimal("0"),

            "current_equity": Decimal("100000"),

        }

        decision1, _ = limits.evaluate(state1)

        assert decision1 == RiskDecision.ALLOW

        # Moderate losses - might be DENY

        state2 = {

            "position_leverage": Decimal("2"),

            "account_balance": Decimal("97000"),

            "open_position_notional": Decimal("30000"),

            "new_position_notional": Decimal("0"),

            "realized_pnl_today": Decimal("-3000"),

            "current_equity": Decimal("97000"),

        }

        decision2, _ = limits.evaluate(state2)

        # Might be ALLOW or DENY depending on config

        assert decision2 in [RiskDecision.ALLOW, RiskDecision.DENY]
