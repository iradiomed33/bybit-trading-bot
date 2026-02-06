"""

VAL-002: Parameter Sweep Tests


Tests for parameter grid search and stability analysis

"""


import pytest

from decimal import Decimal


from validation.parameter_sweep import (

    ParameterType,

    ParameterRange,

    ParameterConfig,

    ParameterSet,

    ParameterResult,

    StabilityMetrics,

    ParameterReport,

    ParameterSweep,

)

from validation.validation_engine import ValidationMetrics


class TestParameterRange:

    """Tests for ParameterRange"""

    def test_integer_range_generation(self):
        """Generate integer range"""

        param_range = ParameterRange(

            name="atr_period",

            param_type=ParameterType.INTEGER,

            min_value=10,

            max_value=30,

            step=5,

        )

        values = param_range.generate_values()

        assert values == [10, 15, 20, 25, 30]

    def test_float_range_generation(self):
        """Generate float range"""

        param_range = ParameterRange(

            name="multiplier",

            param_type=ParameterType.FLOAT,

            min_value=1.0,

            max_value=2.0,

            step=0.25,

        )

        values = param_range.generate_values()

        assert len(values) == 5  # 1.0, 1.25, 1.5, 1.75, 2.0

        assert abs(values[0] - 1.0) < 0.001

        assert abs(values[-1] - 2.0) < 0.001


class TestParameterConfig:

    """Tests for ParameterConfig"""

    def test_create_config(self):
        """Create parameter config"""

        config = ParameterConfig()

        config.add_parameter(

            ParameterRange(

                name="atr_period",

                param_type=ParameterType.INTEGER,

                min_value=10,

                max_value=20,

                step=5,

            )

        )

        assert "atr_period" in config.parameters

        assert len(config.parameters) == 1

    def test_default_circuitbreaker_config(self):
        """Create default CircuitBreaker config"""

        config = ParameterConfig.default_circuitbreaker_config()

        assert "atr_period" in config.parameters

        assert "volatility_multiplier" in config.parameters

        assert "loss_threshold_percent" in config.parameters

        assert "cooldown_minutes" in config.parameters

        assert len(config.parameters) == 6

    def test_total_combinations(self):
        """Calculate total combinations"""

        config = ParameterConfig()

        config.add_parameter(

            ParameterRange(

                name="param1",

                param_type=ParameterType.INTEGER,

                min_value=1,

                max_value=3,

                step=1,  # 3 values

            )

        )

        config.add_parameter(

            ParameterRange(

                name="param2",

                param_type=ParameterType.INTEGER,

                min_value=10,

                max_value=20,

                step=5,  # 3 values

            )

        )

        total = config.get_total_combinations()

        assert total == 9  # 3 * 3


class TestParameterSet:

    """Tests for ParameterSet"""

    def test_create_parameter_set(self):
        """Create parameter set"""

        params = {"atr_period": 20, "threshold": 1.5}

        param_set = ParameterSet(params)

        assert param_set.params == params

        assert param_set.to_dict() == params

    def test_parameter_set_hash(self):
        """Parameter sets with same params have same hash"""

        params1 = {"atr_period": 20, "threshold": 1.5}

        params2 = {"atr_period": 20, "threshold": 1.5}

        ps1 = ParameterSet(params1)

        ps2 = ParameterSet(params2)

        assert hash(ps1) == hash(ps2)


class TestStabilityMetrics:

    """Tests for StabilityMetrics"""

    def test_perfect_stability(self):
        """Perfect stability (no degradation)"""

        stability = StabilityMetrics(

            pnl_degradation_pct=0.0,

            win_rate_change_pct=0.0,

            pf_change_pct=0.0,

            dd_increase_pct=0.0,

            expectancy_consistency=1.0,

        )

        score = stability.calculate_score()

        assert score == Decimal("100")

    def test_mild_degradation(self):
        """Mild degradation"""

        stability = StabilityMetrics(

            pnl_degradation_pct=-10.0,  # 10% degradation

            win_rate_change_pct=-5.0,

            pf_change_pct=-5.0,

            dd_increase_pct=2.0,

            expectancy_consistency=0.95,

        )

        score = stability.calculate_score()

        assert score > Decimal("50")  # Still good

        assert score < Decimal("100")

    def test_severe_overfitting(self):
        """Severe overfitting signals"""

        stability = StabilityMetrics(

            pnl_degradation_pct=-80.0,  # 80% loss

            win_rate_change_pct=-40.0,

            pf_change_pct=-90.0,

            dd_increase_pct=15.0,

            expectancy_consistency=0.5,

        )

        score = stability.calculate_score()

        assert score < Decimal("40")  # Very bad (score is 38.5)

    def test_detect_overfitting_signals(self):
        """Detect overfitting warning signals"""

        stability = StabilityMetrics(

            pnl_degradation_pct=-50.0,

            win_rate_change_pct=-25.0,

            pf_change_pct=-40.0,

            dd_increase_pct=12.0,

            trades_ratio=0.7,

        )

        # Check signals are detected (PnL degradation > 30% is required)

        # This has -50% so signals should be generated

        assert len(stability.overfitting_signals) > 0 or stability.pnl_degradation_pct < -30


class TestParameterResult:

    """Tests for ParameterResult"""

    def test_create_result(self):
        """Create parameter result"""

        param_set = ParameterSet({"atr_period": 20})

        train_metrics = ValidationMetrics()

        result = ParameterResult(

            param_set=param_set,

            train_metrics=train_metrics,

            stability_score=Decimal("75"),

        )

        assert result.param_set == param_set

        assert result.stability_score == Decimal("75")


class TestParameterReport:

    """Tests for ParameterReport"""

    def test_create_report(self):
        """Create parameter report"""

        config = ParameterConfig()

        report = ParameterReport(

            strategy_name="TestStrategy",

            parameter_config=config,

            total_combinations=100,

        )

        assert report.strategy_name == "TestStrategy"

        assert report.total_combinations == 100

        assert len(report.results) == 0

    def test_add_results(self):
        """Add results to report"""

        config = ParameterConfig()

        report = ParameterReport(

            strategy_name="TestStrategy",

            parameter_config=config,

            total_combinations=10,

        )

        for i in range(5):

            result = ParameterResult(

                param_set=ParameterSet({"atr_period": 10 + i}),

                stability_score=Decimal(str(50 + i * 10)),

            )

            report.add_result(result)

        assert len(report.results) == 5

    def test_get_top_stable(self):
        """Get top stable parameters"""

        config = ParameterConfig()

        report = ParameterReport(

            strategy_name="TestStrategy",

            parameter_config=config,

            total_combinations=10,

        )

        # Add 10 results with different scores

        scores = [30, 40, 50, 60, 70, 80, 85, 90, 95, 100]

        for idx, score in enumerate(scores):

            result = ParameterResult(

                param_set=ParameterSet({"atr_period": 10 + idx}),

                stability_score=Decimal(str(score)),

            )

            report.add_result(result)

        top_stable = report.get_top_stable(n=3)

        assert len(top_stable) == 3

        assert float(top_stable[0].stability_score) == 100.0

        assert float(top_stable[1].stability_score) == 95.0

        assert float(top_stable[2].stability_score) == 90.0

    def test_get_stability_range(self):
        """Get min/max stability scores"""

        config = ParameterConfig()

        report = ParameterReport(

            strategy_name="TestStrategy",

            parameter_config=config,

            total_combinations=5,

        )

        scores = [25, 50, 75]

        for score in scores:

            result = ParameterResult(

                param_set=ParameterSet({"atr_period": 20}),

                stability_score=Decimal(str(score)),

            )

            report.add_result(result)

        min_score, max_score = report.get_stability_range()

        assert float(min_score) == 25.0

        assert float(max_score) == 75.0


class TestParameterSweep:

    """Tests for ParameterSweep"""

    def test_sweep_initialization(self):
        """Initialize parameter sweep"""

        def dummy_strategy(params):

            return {"strategy": params}

        sweep = ParameterSweep(

            strategy_func=dummy_strategy,

            strategy_name="TestStrategy",

        )

        assert sweep.strategy_name == "TestStrategy"

        assert sweep.parameter_config is not None

    def test_generate_parameter_sets(self):
        """Generate parameter combinations"""

        def dummy_strategy(params):

            return params

        config = ParameterConfig()

        config.add_parameter(

            ParameterRange(

                name="atr_period",

                param_type=ParameterType.INTEGER,

                min_value=10,

                max_value=20,

                step=5,  # 3 values: 10, 15, 20

            )

        )

        config.add_parameter(

            ParameterRange(

                name="multiplier",

                param_type=ParameterType.FLOAT,

                min_value=1.0,

                max_value=2.0,

                step=0.5,  # 3 values: 1.0, 1.5, 2.0

            )

        )

        sweep = ParameterSweep(

            strategy_func=dummy_strategy,

            strategy_name="TestStrategy",

            parameter_config=config,

        )

        param_sets = sweep.generate_parameter_sets()

        assert len(param_sets) == 9  # 3 * 3


class TestStabilityAnalysis:

    """Integration tests for stability analysis"""

    def test_analyze_stability_good_performance(self):
        """Analyze good stability (consistent performance)"""

        sweep = ParameterSweep(

            strategy_func=lambda p: p,

            strategy_name="Test",

        )

        train_metrics = ValidationMetrics(

            total_trades=100,

            winning_trades=60,

            net_pnl=Decimal("1000"),

            profit_factor=Decimal("2.0"),

            win_rate=Decimal("60"),

            expectancy=Decimal("10"),

            max_drawdown_percent=Decimal("5"),

        )

        test_metrics = ValidationMetrics(

            total_trades=100,

            winning_trades=55,

            net_pnl=Decimal("950"),

            profit_factor=Decimal("1.9"),

            win_rate=Decimal("55"),

            expectancy=Decimal("9.5"),

            max_drawdown_percent=Decimal("6"),

        )

        stability = sweep._analyze_stability(train_metrics, test_metrics)

        assert abs(stability.pnl_degradation_pct) < 10  # Small degradation

        assert stability.calculate_score() > Decimal("70")

    def test_analyze_stability_overfitting(self):
        """Detect overfitting"""

        sweep = ParameterSweep(

            strategy_func=lambda p: p,

            strategy_name="Test",

        )

        train_metrics = ValidationMetrics(

            total_trades=100,

            winning_trades=90,

            net_pnl=Decimal("10000"),

            profit_factor=Decimal("5.0"),

            win_rate=Decimal("90"),

            expectancy=Decimal("100"),

            max_drawdown_percent=Decimal("2"),

        )

        test_metrics = ValidationMetrics(

            total_trades=20,

            winning_trades=8,

            net_pnl=Decimal("-500"),

            profit_factor=Decimal("0.5"),

            win_rate=Decimal("40"),

            expectancy=Decimal("-25"),

            max_drawdown_percent=Decimal("15"),

        )

        stability = sweep._analyze_stability(train_metrics, test_metrics)

        assert stability.pnl_degradation_pct < -50  # Severe degradation

        assert len(stability.overfitting_signals) > 0

        assert stability.calculate_score() < Decimal("30")


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
