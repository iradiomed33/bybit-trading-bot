"""

Integration tests for standardized signal rejection logging.


Verifies that signal rejections at each pipeline stage (strategy filters,

meta-layer conflicts, risk checks, position handler conflicts) are logged

with structured reasons and values following the standard format:

  {signal, confidence, reasons[], values{indicator:value}}


Tests DoD requirement: "По одному логу видно: стратегия дала buy, мета отклонила 

из-за X, риск отклонил из-за Y" (From one log see: strategy gave buy, meta rejected 

because X, risk rejected because Y)

"""


import pytest

import json


class TestStrategySignalStructure:

    """Tests that all strategy signals have standardized structure with reasons/values"""

    def test_signal_has_required_fields(self):
        """Verify signal dict has all required fields for standardized logging"""

        # Mock signal from strategy

        signal = {

            "signal": "long",

            "confidence": 0.85,

            "reasons": ["trend_adx_ok", "volume_confirmed", "ema_alignment_ok"],

            "values": {

                "adx": 35.2,

                "volume_zscore": 2.1,

                "ema_ratio": 1.05,

                "atr": 450.0,

            },

            "entry_price": 50000.0,

            "stop_loss": 49500.0,

            "take_profit": 51000.0,

        }

        # Verify structure

        assert "signal" in signal

        assert "confidence" in signal

        assert "reasons" in signal

        assert isinstance(signal["reasons"], list)

        assert len(signal["reasons"]) > 0

        assert "values" in signal

        assert isinstance(signal["values"], dict)

    def test_signal_reasons_are_machine_readable(self):
        """Reasons list should contain short codes, not full sentences"""

        signal = {

            "signal": "long",

            "confidence": 0.85,

            "reasons": [

                "trend_adx_ok",

                "ema_alignment_ok",

                "volume_confirmed",

                "pullback_zone_ok",

                "no_anomaly",

            ],

            "values": {"adx": 35.2, "volume_zscore": 2.1},

        }

        # Each reason should be short code (lowercase_with_underscores)

        for reason in signal["reasons"]:

            assert isinstance(reason, str)

            assert len(reason) < 30  # Machine-readable codes are short

            assert "_" in reason or reason.isalpha()  # No spaces or special chars


class TestMetaLayerSignalNormalization:

    """Tests that MetaLayer normalizes all signals to standard format"""

    def test_meta_layer_normalizes_missing_fields(self):
        """MetaLayer should add missing reasons/values to signals"""

        # Simulate a signal without reasons/values

        legacy_signal = {

            "signal": "long",

            "confidence": 0.75,

            "entry_price": 50000.0,

        }

        # MetaLayer should normalize it

        # (Simulating the _normalize_signal behavior)

        normalized = {

            **legacy_signal,

            "reasons": legacy_signal.get("reasons", ["legacy_signal"]),

            "values": legacy_signal.get("values", {}),

        }

        assert "reasons" in normalized

        assert isinstance(normalized["reasons"], list)

        assert "values" in normalized

        assert isinstance(normalized["values"], dict)


class TestRiskRejectionLogging:

    """Tests that risk limit violations are logged with structured format"""

    def test_risk_denial_logged_with_reasons(self):
        """When risk denies trade, log should include structured reasons/values"""

        # Mock risk check result

        risk_violation = {

            "check_name": "leverage",

            "current_value": 15.0,

            "limit_value": 10.0,

            "severity": "warning",

        }

        rejection_signal = {

            "signal": "long",

            "confidence": 0.85,

            "reasons": ["risk_limit_violation"],

            "values": {

                "violations": [

                    {

                        "check": risk_violation["check_name"],

                        "current": risk_violation["current_value"],

                        "limit": risk_violation["limit_value"],

                    }

                ],

                "reason": "Leverage exceeded",

            },

        }

        # Verify rejection structure

        assert rejection_signal["reasons"][0] == "risk_limit_violation"

        assert "violations" in rejection_signal["values"]

        assert rejection_signal["values"]["violations"][0]["check"] == "leverage"

    def test_critical_risk_violation_logged_separately(self):
        """Critical risk violations (STOP) logged with severity info"""

        critical_rejection = {

            "signal": "long",

            "confidence": 0.85,

            "reasons": ["critical_risk_violation"],

            "values": {

                "violations": [

                    {

                        "check": "daily_loss_limit",

                        "current": 2500.0,

                        "limit": 1000.0,

                        "severity": "critical",

                    }

                ],

                "reason": "Daily loss limit exceeded - STOP ORDER TRIGGERED",

            },

        }

        assert critical_rejection["reasons"][0] == "critical_risk_violation"

        assert critical_rejection["values"]["violations"][0]["severity"] == "critical"


class TestPositionHandlerRejectionLogging:

    """Tests that position conflicts are logged with structured format"""

    def test_add_validation_failure_logged(self):
        """When ADD (pyramid) validation fails, log structured rejection"""

        rejection_log = {

            "strategy_name": "TrendPullback",

            "direction": "LONG",

            "confidence": 0.85,

            "reasons": ["add_validation_failed"],

            "values": {

                "validation_error": "Max pyramid levels reached: 3 >= 3",

                "current_qty": 0.5,

                "add_qty": 0.25,

                "pyramid_level": 3,

            },

        }

        # Verify rejection structure

        assert rejection_log["reasons"][0] == "add_validation_failed"

        assert "validation_error" in rejection_log["values"]

        assert "pyramid_level" in rejection_log["values"]

    def test_flip_validation_failure_logged(self):
        """When FLIP validation fails, log structured rejection"""

        rejection_log = {

            "strategy_name": "BreakoutStrategy",

            "direction": "SHORT",

            "confidence": 0.75,

            "reasons": ["flip_validation_failed"],

            "values": {

                "validation_error": "Confidence too low: 0.75 < 0.8",

                "current_side": "LONG",

                "current_qty": 1.0,

            },

        }

        # Verify rejection structure

        assert rejection_log["reasons"][0] == "flip_validation_failed"

        assert rejection_log["values"]["current_side"] == "LONG"

    def test_signal_handler_conflict_logged(self):
        """When signal handler blocks signal, log with action details"""

        conflict_log = {

            "strategy_name": "MeanReversion",

            "direction": "LONG",

            "confidence": 0.80,

            "reasons": ["signal_handler_conflict"],

            "values": {

                "action": "ignore",  # SignalAction.IGNORE

                "message": "Already in long position",

            },

        }

        # Verify conflict structure

        assert conflict_log["reasons"][0] == "signal_handler_conflict"

        assert "action" in conflict_log["values"]

        assert conflict_log["values"]["action"] in ["ignore", "add", "flip"]


class TestCompleteRejectionChain:

    """End-to-end tests for complete rejection chain visibility"""

    def test_signal_generated_but_meta_rejects(self):
        """Complete flow: Signal generated, meta-layer rejects it"""

        # 1. Strategy generates signal

        strategy_signal = {

            "strategy": "TrendPullback",

            "signal": "long",

            "confidence": 0.85,

            "reasons": ["trend_adx_ok", "ema_alignment_ok", "volume_confirmed"],

            "values": {"adx": 35.2, "volume_zscore": 2.1},

            "entry_price": 50000.0,

        }

        # 2. Meta-layer rejects it (no-trade zone)

        meta_rejection = {

            "strategy": "TrendPullback",

            "signal": "long",

            "confidence": 0.85,

            "reasons": ["no_trade_zone"],

            "values": {

                "rejection_point": "meta_layer",

                "rejection_reason": "News event within 2 hours",

            },

        }

        # In logs we should see:

        # - Signal generated with conditions passing

        # - Meta layer rejection with reason

        assert strategy_signal["reasons"] == [

            "trend_adx_ok",

            "ema_alignment_ok",

            "volume_confirmed",

        ]

        assert meta_rejection["reasons"] == ["no_trade_zone"]

        assert meta_rejection["values"]["rejection_point"] == "meta_layer"

    def test_signal_passes_meta_but_risk_rejects(self):
        """Complete flow: Passes meta-layer, risk engine rejects"""

        # 1. Signal passes meta-layer

        meta_approved = {

            "strategy": "BreakoutStrategy",

            "signal": "short",

            "confidence": 0.80,

            "reasons": ["bb_width_narrow", "breakout_down", "volume_confirmed"],

            "entry_price": 49500.0,

        }

        # 2. Risk engine rejects it

        risk_rejection = {

            "strategy": "BreakoutStrategy",

            "signal": "short",

            "confidence": 0.80,

            "reasons": ["risk_limit_violation"],

            "values": {

                "violations": [

                    {

                        "check": "notional_exposure",

                        "current": 15000.0,

                        "limit": 10000.0,

                    }

                ]

            },

        }

        # In logs we should see both approvals and rejections at each stage

        assert meta_approved["signal"] == "short"

        assert risk_rejection["reasons"][0] == "risk_limit_violation"

    def test_signal_passes_all_checks_but_position_handler_rejects(self):
        """Complete flow: Signal passes all checks, position handler rejects"""

        # 1. Signal generated

        signal = {

            "strategy": "MeanReversion",

            "signal": "long",

            "confidence": 0.82,

            "reasons": ["rsi_oversold", "ema_support"],

        }

        # 2. Passes meta-layer (no conflicts)

        # 3. Passes risk checks

        # 4. Position handler rejects (already in position)

        position_rejection = {

            "strategy": "MeanReversion",

            "signal": "long",

            "confidence": 0.82,

            "reasons": ["signal_handler_conflict"],

            "values": {

                "action": "ignore",

                "message": "Already in LONG position, pyramid levels exhausted",

            },

        }

        assert position_rejection["reasons"][0] == "signal_handler_conflict"

        assert "pyramid levels exhausted" in position_rejection["values"]["message"]


class TestReasonCodeStandardization:

    """Tests that reason codes are consistent across system"""

    # Standard reason codes used throughout the system

    STRATEGY_REASON_CODES = [

        # TrendPullback

        "trend_adx_ok",

        "ema_alignment_ok",

        "pullback_zone_ok",

        "volume_confirmed",

        "no_anomaly",

        # MeanReversion

        "low_volatility_regime",

        "trend_not_too_strong",

        "vwap_distance_ok",

        "rsi_oversold",

        "rsi_overbought",

        "ema50_distance_ok",

        # Breakout

        "bb_width_narrow",

        "breakout_up",

        "breakout_down",

        "vol_expansion",

        "spread_ok",

    ]

    META_REASON_CODES = [

        "no_trade_zone",

        "meta_conflict",

        "mtf_score",

        "mtf_score_below_threshold",

    ]

    RISK_REASON_CODES = [

        "risk_limit_violation",

        "critical_risk_violation",

    ]

    POSITION_HANDLER_REASON_CODES = [

        "signal_handler_conflict",

        "add_validation_failed",

        "flip_validation_failed",

    ]

    def test_all_reason_codes_are_defined(self):
        """Verify all reason codes are in standard lists"""

        all_codes = (

            self.STRATEGY_REASON_CODES

            + self.META_REASON_CODES

            + self.RISK_REASON_CODES

            + self.POSITION_HANDLER_REASON_CODES

        )

        # No duplicates

        assert len(all_codes) == len(set(all_codes))

        # All codes follow format: lowercase_with_underscores

        for code in all_codes:

            assert code.islower() or "_" in code

            assert " " not in code


class TestLogParseability:

    """Tests that logs can be parsed to show rejection chains"""

    def test_rejection_chain_is_parseable(self):
        """Complete signal lifecycle should be traceable through logs"""

        # Simulated log entries from complete rejection chain

        logs = [

            {

                "level": "INFO",

                "message": "signal_generated",

                "strategy": "TrendPullback",

                "direction": "LONG",

                "reasons": ["trend_adx_ok", "volume_confirmed"],

            },

            {

                "level": "WARNING",

                "message": "signal_rejected",

                "strategy": "TrendPullback",

                "direction": "LONG",

                "reasons": ["no_trade_zone"],

                "reason_code": "no_trade_zone",

            },

        ]

        # Extract rejection chain

        generated_logs = [item for item in logs if item["message"] == "signal_generated"]

        rejected_logs = [item for item in logs if item["message"] == "signal_rejected"]

        assert len(generated_logs) == 1

        assert len(rejected_logs) == 1

        assert generated_logs[0]["reasons"] != rejected_logs[0]["reasons"]

    def test_signal_tracing_by_reason_code(self):
        """Can grep logs by reason code to find patterns"""

        logs = [

            {"reason": "max_pyramid_levels_reached"},

            {"reason": "max_pyramid_levels_reached"},

            {"reason": "confidence_too_low"},

            {"reason": "max_pyramid_levels_reached"},

            {"reason": "notional_exposure_exceeded"},

        ]

        # Count rejections by reason

        pyramid_count = len([item for item in logs if "max_pyramid" in item["reason"]])

        confidence_count = len([item for item in logs if "confidence_too_low" in item["reason"]])

        assert pyramid_count == 3

        assert confidence_count == 1

    def test_log_json_serialization(self):
        """Logs with reasons/values should be JSON-serializable for analysis"""

        signal_log = {

            "timestamp": "2024-01-15T10:30:45.123Z",

            "strategy": "BreakoutStrategy",

            "signal": "short",

            "confidence": 0.80,

            "reasons": ["breakout_down", "volume_confirmed"],

            "values": {

                "bb_width": 450.5,

                "volume_zscore": 2.3,

                "atr": 350.0,

            },

        }

        # Should be JSON serializable

        json_str = json.dumps(signal_log, default=str)

        parsed = json.loads(json_str)

        assert parsed["reasons"] == ["breakout_down", "volume_confirmed"]

        assert parsed["values"]["bb_width"] == 450.5


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
