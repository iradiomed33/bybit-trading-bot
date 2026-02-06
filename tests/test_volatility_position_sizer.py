"""

Tests for Volatility-Scaled Position Sizing - D3 EPIC


Covers:

1. Position sizing with different ATR values

2. USD risk stability across volatility regimes

3. Inverse volatility relationship (high ATR → lower qty)

4. Fallback to percent-based sizing

5. Min/max position constraints

6. Configuration management

7. Edge cases and validation

"""


import pytest

from decimal import Decimal


from risk.volatility_position_sizer import (

    VolatilityPositionSizer,

    VolatilityPositionSizerConfig,

)


class TestVolatilityPositionSizerConfig:

    """Test configuration object."""

    def test_default_config(self):
        """Config should have sensible defaults."""

        config = VolatilityPositionSizerConfig()

        assert config.risk_percent == Decimal("1.0")

        assert config.atr_multiplier == Decimal("2.0")

        assert config.min_position_size == Decimal("0.00001")

        assert config.max_position_size == Decimal("100.0")

        assert config.use_percent_fallback is True

    def test_custom_config(self):
        """Config should accept custom values."""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("2.0"),

            atr_multiplier=Decimal("3.0"),

            min_position_size=Decimal("0.01"),

            max_position_size=Decimal("50.0"),

        )

        assert config.risk_percent == Decimal("2.0")

        assert config.atr_multiplier == Decimal("3.0")

        assert config.min_position_size == Decimal("0.01")

        assert config.max_position_size == Decimal("50.0")


class TestPositionSizingBasics:

    """Test basic position sizing calculations."""

    def test_sizing_with_atr(self):
        """Should calculate position size with ATR."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("1.0")))

        account = Decimal("10000")

        entry_price = Decimal("50000")

        atr = Decimal("500")  # $500 volatility

        qty, details = sizer.calculate_position_size(account, entry_price, atr)

        assert qty > 0

        assert details["method"] == "volatility"

        assert details["atr"] == 500.0

        assert details["risk_usd"] == 100.0  # 1% of $10k

    def test_sizing_without_atr_fallback(self):
        """Should use fallback sizing without ATR."""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("1.0"), percent_fallback=Decimal("5.0"), use_percent_fallback=True

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("10000")

        entry_price = Decimal("50000")

        qty, details = sizer.calculate_position_size(account, entry_price, atr=None)

        assert qty > 0

        assert details["method"] == "fallback"

    def test_sizing_no_atr_no_fallback(self):
        """Should return 0 if no ATR and fallback disabled."""

        config = VolatilityPositionSizerConfig(use_percent_fallback=False)

        sizer = VolatilityPositionSizer(config)

        qty, details = sizer.calculate_position_size(Decimal("10000"), Decimal("50000"), atr=None)

        assert qty == Decimal("0")

        assert "error" in details


class TestUsdRiskStability:

    """Test that USD risk remains stable across volatility regimes."""

    def test_usd_risk_same_with_different_volatility(self):
        """USD risk should be constant; qty should vary inversely with ATR."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("1.0")))

        account = Decimal("100000")

        entry_price = Decimal("50000")

        target_risk_usd = Decimal("1000")  # 1% of $100k

        # Scenario 1: Low volatility (ATR = $200)

        qty_low_vol, details_low = sizer.calculate_position_size(

            account, entry_price, atr=Decimal("200")

        )

        # Scenario 2: High volatility (ATR = $500)

        qty_high_vol, details_high = sizer.calculate_position_size(

            account, entry_price, atr=Decimal("500")

        )

        # USD risk should be same

        assert details_low["risk_usd"] == details_high["risk_usd"]

        assert details_low["risk_usd"] == 1000.0

        # Qty should be different (inverse relationship)

        assert qty_low_vol > qty_high_vol

        logger_info = (

            f"Low Vol (ATR=200): qty={qty_low_vol}, " f"High Vol (ATR=500): qty={qty_high_vol}"

        )

        print(logger_info)

    def test_usd_risk_calculation(self):
        """USD risk should equal account * risk_percent / 100."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("2.0")))

        account = Decimal("50000")

        risk_usd = sizer.calculate_risk_dollars(account)

        # 2% of $50k = $1000

        assert float(risk_usd) == 1000.0

    def test_risk_consistency_multiple_accounts(self):
        """Percentage risk should scale with account size."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("1.0")))

        # Small account

        qty_small, details_small = sizer.calculate_position_size(

            Decimal("10000"), Decimal("50000"), atr=Decimal("500")

        )

        # Large account (10x bigger)

        qty_large, details_large = sizer.calculate_position_size(

            Decimal("100000"), Decimal("50000"), atr=Decimal("500")

        )

        # USD risk should scale with account

        assert details_large["risk_usd"] == details_small["risk_usd"] * 10

        # Qty should also scale (same ATR, same entry)

        assert float(qty_large) > float(qty_small)


class TestInverseVolatilityRelationship:

    """Test inverse relationship: high volatility → lower qty."""

    def test_higher_atr_lower_qty(self):
        """Higher ATR should result in lower position qty."""

        sizer = VolatilityPositionSizer(

            VolatilityPositionSizerConfig(

                risk_percent=Decimal("2.0"), atr_multiplier=Decimal("2.0")

            )

        )

        account = Decimal("100000")

        entry_price = Decimal("50000")

        # Low ATR

        qty_low, _ = sizer.calculate_position_size(account, entry_price, atr=Decimal("100"))

        # High ATR (2x)

        qty_high, _ = sizer.calculate_position_size(account, entry_price, atr=Decimal("200"))

        # Higher ATR should give lower qty

        assert qty_high < qty_low

        # For same account and entry, qty should be inversely proportional to ATR

        ratio = float(qty_low) / float(qty_high)

        # Ratio should be approximately 2:1 (since ATR doubled)

        assert 1.9 < ratio < 2.1

    def test_atr_doubling_halves_qty(self):
        """Doubling ATR should approximately halve qty (same risk)."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("2.0")))

        account = Decimal("100000")

        entry_price = Decimal("40000")

        qty1, _ = sizer.calculate_position_size(account, entry_price, atr=Decimal("200"))

        qty2, _ = sizer.calculate_position_size(account, entry_price, atr=Decimal("400"))

        # qty2 should be about half of qty1

        ratio = float(qty1) / float(qty2)

        assert 1.8 < ratio < 2.3


class TestConstraints:

    """Test min/max position constraints."""

    def test_min_position_constraint(self):
        """Position should not go below minimum."""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("0.1"), min_position_size=Decimal("0.01")  # Very small risk

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("1000")

        entry_price = Decimal("50000")

        atr = Decimal("5000")  # Very high ATR

        qty, details = sizer.calculate_position_size(account, entry_price, atr)

        # Should be clamped to min

        assert qty >= config.min_position_size

        assert details["constrained"] is True

    def test_max_position_constraint(self):
        """Position should not exceed maximum."""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("10.0"), max_position_size=Decimal("0.001")

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("100000")

        entry_price = Decimal("50000")

        atr = Decimal("50")  # Very low ATR - will generate qty >> max

        qty, details = sizer.calculate_position_size(account, entry_price, atr)

        # Should be clamped to max

        assert qty <= config.max_position_size

        assert details["constrained"] is True


class TestFallbackSizing:

    """Test percent-based fallback sizing."""

    def test_fallback_percentage(self):
        """Fallback should use percent of account."""

        config = VolatilityPositionSizerConfig(

            percent_fallback=Decimal("3.0"), use_percent_fallback=True

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("100000")

        entry_price = Decimal("50000")

        qty, details = sizer.calculate_position_size(account, entry_price, atr=None)

        # 3% of $100k = $3k / $50k entry = 0.06 BTC

        expected_qty = Decimal("100000") * Decimal("3.0") / 100 / Decimal("50000")

        assert float(qty) == pytest.approx(float(expected_qty), rel=0.01)

        assert details["method"] == "fallback"


class TestPositionValidation:

    """Test position validation."""

    def test_validate_valid_position(self):
        """Valid position should pass validation."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("1.0")))

        is_valid, message = sizer.validate_position_size(

            position_qty=Decimal("0.05"),

            account_balance=Decimal("100000"),

            entry_price=Decimal("50000"),

            distance_to_sl=Decimal("500"),

        )

        assert is_valid is True

    def test_validate_zero_quantity(self):
        """Zero quantity should fail."""

        sizer = VolatilityPositionSizer()

        is_valid, message = sizer.validate_position_size(

            position_qty=Decimal("0"),

            account_balance=Decimal("100000"),

            entry_price=Decimal("50000"),

            distance_to_sl=Decimal("500"),

        )

        assert is_valid is False

        assert "must be > 0" in message

    def test_validate_excessive_leverage(self):
        """Excessive leverage should fail."""

        sizer = VolatilityPositionSizer()

        is_valid, message = sizer.validate_position_size(

            position_qty=Decimal("100"),  # Huge

            account_balance=Decimal("10000"),

            entry_price=Decimal("50000"),

            distance_to_sl=Decimal("100"),

        )

        # 100 * $50k = $5M position on $10k account

        assert is_valid is False

        # Either risk or leverage check should fail

        assert "risk" in message.lower() or "leverage" in message.lower()


class TestEdgeCases:

    """Test edge cases and error conditions."""

    def test_zero_account_balance(self):
        """Should handle zero account balance."""

        sizer = VolatilityPositionSizer()

        qty, details = sizer.calculate_position_size(

            Decimal("0"), Decimal("50000"), atr=Decimal("500")

        )

        assert qty == Decimal("0")

        assert "error" in details

    def test_negative_account_balance(self):
        """Should handle negative account balance."""

        sizer = VolatilityPositionSizer()

        qty, details = sizer.calculate_position_size(

            Decimal("-10000"), Decimal("50000"), atr=Decimal("500")

        )

        assert qty == Decimal("0")

        assert "error" in details

    def test_zero_entry_price(self):
        """Should handle zero entry price."""

        sizer = VolatilityPositionSizer()

        qty, details = sizer.calculate_position_size(

            Decimal("10000"), Decimal("0"), atr=Decimal("500")

        )

        assert qty == Decimal("0")

        assert "error" in details

    def test_very_large_values(self):
        """Should handle very large values."""

        sizer = VolatilityPositionSizer()

        qty, details = sizer.calculate_position_size(

            Decimal("1000000000"),  # $1B account

            Decimal("100000"),  # $100k entry

            atr=Decimal("10000"),  # $10k ATR

        )

        assert qty > 0

        assert "error" not in details

    def test_very_small_atr(self):
        """Should handle very small ATR."""

        sizer = VolatilityPositionSizer(

            VolatilityPositionSizerConfig(max_position_size=Decimal("1.0"))

        )

        qty, details = sizer.calculate_position_size(

            Decimal("10000"), Decimal("50000"), atr=Decimal("0.1")  # Very small ATR

        )

        # Should be constrained to max

        assert qty <= Decimal("1.0")


class TestConfigurationManagement:

    """Test config updates."""

    def test_update_risk_percent(self):
        """Should update risk percent."""

        sizer = VolatilityPositionSizer()

        # Default 1%, larger account

        qty1, details1 = sizer.calculate_position_size(

            Decimal("100000"), Decimal("50000"), atr=Decimal("500")

        )

        # Update to 2%

        sizer.update_config(risk_percent=Decimal("2.0"))

        qty2, details2 = sizer.calculate_position_size(

            Decimal("100000"), Decimal("50000"), atr=Decimal("500")

        )

        # 2% risk should give 2x the qty (same ATR)

        assert float(qty2) > float(qty1)

    def test_get_details(self):
        """Should return calculation details."""

        sizer = VolatilityPositionSizer()

        sizer.calculate_position_size(Decimal("10000"), Decimal("50000"), atr=Decimal("500"))

        details = sizer.get_details()

        assert "last_calculation" in details

        assert "config" in details

        assert details["config"]["risk_percent"] == 1.0


class TestRealWorldScenarios:

    """Test realistic trading scenarios."""

    def test_btc_volatility_change(self):
        """Simulate BTC trading with changing volatility."""

        sizer = VolatilityPositionSizer(

            VolatilityPositionSizerConfig(

                risk_percent=Decimal("1.0"),

                atr_multiplier=Decimal("2.0"),

            )

        )

        account = Decimal("50000")

        entry_price = Decimal("40000")

        # Calm market

        qty_calm, details_calm = sizer.calculate_position_size(

            account, entry_price, atr=Decimal("200")

        )

        # Volatile market

        qty_volatile, details_volatile = sizer.calculate_position_size(

            account, entry_price, atr=Decimal("800")

        )

        # Same risk, different qty

        assert details_calm["risk_usd"] == details_volatile["risk_usd"]

        assert qty_calm > qty_volatile

        print(f"Calm market: qty={qty_calm}, risk=${details_calm['risk_usd']}")

        print(f"Volatile market: qty={qty_volatile}, risk=${details_volatile['risk_usd']}")

    def test_multiple_trades_same_risk(self):
        """Multiple trades should maintain risk percentage."""

        sizer = VolatilityPositionSizer(VolatilityPositionSizerConfig(risk_percent=Decimal("1.0")))

        account = Decimal("100000")

        trades = [

            (Decimal("30000"), Decimal("300")),  # ETHUSDT, low ATR

            (Decimal("50000"), Decimal("400")),  # BTCUSDT, med ATR

            (Decimal("60000"), Decimal("800")),  # ALTUSDT, high ATR

        ]

        risks = []

        for entry_price, atr in trades:

            qty, details = sizer.calculate_position_size(account, entry_price, atr)

            risks.append(details["risk_usd"])

            print(f"Entry={entry_price}, ATR={atr}, qty={qty}, risk=${details['risk_usd']}")

        # All should have same USD risk

        for risk in risks:

            assert risk == pytest.approx(1000.0, rel=0.01)
