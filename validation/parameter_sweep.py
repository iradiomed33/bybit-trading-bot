"""

VAL-002: Parameter Sweep with Stability Analysis


Prevents overfitting through robust parameter selection:

- Grid search across parameter ranges

- Stability analysis (train vs test degradation)

- Identifies range of stable parameters, not just "best"

- Detects curve fitting warning signs

"""


from dataclasses import dataclass, field

from typing import Dict, List, Tuple, Optional, Any, Callable

from decimal import Decimal

from datetime import datetime

import json

from enum import Enum

import pandas as pd

import logging


logger = logging.getLogger(__name__)


class ParameterType(str, Enum):

    """Parameter types for range definition"""

    INTEGER = "integer"

    FLOAT = "float"

    DECIMAL = "decimal"


@dataclass
class ParameterRange:

    """Single parameter range definition"""

    name: str

    param_type: ParameterType

    min_value: float

    max_value: float

    step: float

    description: str = ""

    def generate_values(self) -> List[float]:
        """Generate all values in range"""

        if self.param_type == ParameterType.INTEGER:

            return list(range(int(self.min_value), int(self.max_value) + 1, int(self.step)))

        else:

            values = []

            current = self.min_value

            while current <= self.max_value:

                values.append(current)

                current += self.step

            return values


@dataclass
class ParameterConfig:

    """Parameter configuration for sweep"""

    parameters: Dict[str, ParameterRange] = field(default_factory=dict)

    @staticmethod
    def default_circuitbreaker_config() -> "ParameterConfig":
        """Default CircuitBreaker parameters for sweep"""

        config = ParameterConfig()

        config.parameters = {

            "atr_period": ParameterRange(

                name="atr_period",

                param_type=ParameterType.INTEGER,

                min_value=10,

                max_value=50,

                step=5,

                description="ATR lookback period",

            ),

            "volatility_multiplier": ParameterRange(

                name="volatility_multiplier",

                param_type=ParameterType.FLOAT,

                min_value=1.5,

                max_value=3.0,

                step=0.25,

                description="ATR multiplier for volatility threshold",

            ),

            "volatility_threshold_percent": ParameterRange(

                name="volatility_threshold_percent",

                param_type=ParameterType.FLOAT,

                min_value=2.0,

                max_value=5.0,

                step=0.5,

                description="Volatility threshold in percent",

            ),

            "loss_threshold_percent": ParameterRange(

                name="loss_threshold_percent",

                param_type=ParameterType.FLOAT,

                min_value=2.0,

                max_value=5.0,

                step=0.5,

                description="Daily loss threshold to trigger halt",

            ),

            "loss_window_candles": ParameterRange(

                name="loss_window_candles",

                param_type=ParameterType.INTEGER,

                min_value=20,

                max_value=100,

                step=20,

                description="Candles for loss calculation window",

            ),

            "cooldown_minutes": ParameterRange(

                name="cooldown_minutes",

                param_type=ParameterType.INTEGER,

                min_value=5,

                max_value=30,

                step=5,

                description="Cooldown time after circuit breaker activation",

            ),

        }

        return config

    def add_parameter(self, param_range: ParameterRange) -> None:
        """Add parameter to config"""

        self.parameters[param_range.name] = param_range

    def get_total_combinations(self) -> int:
        """Get total number of parameter combinations"""

        total = 1

        for param in self.parameters.values():

            values = param.generate_values()

            total *= len(values)

        return total


@dataclass
class ParameterSet:

    """Single set of parameter values"""

    params: Dict[str, float]

    combination_index: int = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dict"""

        return self.params.copy()

    def __hash__(self):

        return hash(tuple(sorted(self.params.items())))

    def __eq__(self, other):

        if not isinstance(other, ParameterSet):

            return False

        return self.params == other.params


@dataclass
class ParameterResult:

    """Result for single parameter set"""

    param_set: ParameterSet

    train_metrics: Optional[Any] = None

    test_metrics: Optional[Any] = None

    stability_score: Decimal = field(default_factory=lambda: Decimal("0"))

    degradation_metrics: Dict[str, float] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)


@dataclass
class StabilityMetrics:

    """Stability analysis between train and test"""

    pnl_degradation_pct: float = 0.0  # (test - train) / train * 100

    win_rate_change_pct: float = 0.0  # Change in win rate

    pf_change_pct: float = 0.0  # Change in profit factor

    dd_increase_pct: float = 0.0  # Increase in drawdown

    expectancy_consistency: float = 1.0  # test_exp / train_exp (closer to 1 is better)

    trades_ratio: float = 1.0  # test_trades / train_trades

    # Composite stability score (0-100)

    stability_score: Decimal = field(default_factory=lambda: Decimal("50"))

    # Overfitting signals

    overfitting_signals: List[str] = field(default_factory=list)

    def calculate_score(self) -> Decimal:
        """Calculate composite stability score (0-100)"""

        # Start with 100

        score = Decimal("100")

        # Penalize PnL degradation (larger penalty for worse degradation)

        pnl_penalty = abs(Decimal(str(self.pnl_degradation_pct))) * Decimal("0.3")

        score -= pnl_penalty

        # Penalize win rate reduction

        wr_penalty = max(Decimal("0"), -Decimal(str(self.win_rate_change_pct))) * Decimal("0.2")

        score -= wr_penalty

        # Penalize profit factor reduction

        pf_penalty = max(Decimal("0"), -Decimal(str(self.pf_change_pct))) * Decimal("0.2")

        score -= pf_penalty

        # Penalize drawdown increase

        dd_penalty = Decimal(str(self.dd_increase_pct)) * Decimal("0.1")

        score -= dd_penalty

        # Penalize expectancy inconsistency

        exp_consistency_penalty = abs(

            Decimal("1") - Decimal(str(self.expectancy_consistency))

        ) * Decimal("20")

        score -= exp_consistency_penalty

        # Ensure score is in [0, 100]

        score = max(Decimal("0"), min(Decimal("100"), score))

        return score


@dataclass
class ParameterReport:

    """Parameter sweep report"""

    strategy_name: str

    parameter_config: ParameterConfig

    total_combinations: int

    results: List[ParameterResult] = field(default_factory=list)

    top_stable_params: List[ParameterResult] = field(default_factory=list)

    generated_at: datetime = field(default_factory=datetime.now)

    sweep_duration_seconds: float = 0.0

    def add_result(self, result: ParameterResult) -> None:
        """Add sweep result"""

        self.results.append(result)

    def get_top_stable(self, n: int = 10) -> List[ParameterResult]:
        """Get top N stable parameter sets"""

        sorted_results = sorted(

            self.results,

            key=lambda r: r.stability_score,

            reverse=True,

        )

        self.top_stable_params = sorted_results[:n]

        return self.top_stable_params

    def get_stability_range(self) -> Tuple[Decimal, Decimal]:
        """Get min/max stability scores"""

        if not self.results:

            return Decimal("0"), Decimal("100")

        scores = [r.stability_score for r in self.results]

        return min(scores), max(scores)

    def export_json(self) -> str:
        """Export report to JSON"""

        def decimal_to_float(obj):

            if isinstance(obj, Decimal):

                return float(obj)

            elif isinstance(obj, datetime):

                return obj.isoformat()

            elif isinstance(obj, (ParameterSet, StabilityMetrics)):

                return obj.__dict__

            raise TypeError

        report_dict = {

            "strategy_name": self.strategy_name,

            "total_combinations": self.total_combinations,

            "combinations_evaluated": len(self.results),

            "sweep_duration_seconds": self.sweep_duration_seconds,

            "generated_at": self.generated_at.isoformat(),

            "top_stable_parameters": [

                {

                    "params": r.param_set.to_dict(),

                    "train_p": float(r.train_metrics.profit_factor) if r.train_metrics else None,

                    "test_p": float(r.test_metrics.profit_factor) if r.test_metrics else None,

                    "stability_score": float(r.stability_score),

                    "degradation": r.degradation_metrics,

                }

                for r in self.top_stable_params

            ],

            "stability_stats": {

                "min_score": float(

                    min(r.stability_score for r in self.results) if self.results else 0

                ),

                "max_score": float(

                    max(r.stability_score for r in self.results) if self.results else 100

                ),

                "avg_score": float(

                    sum(r.stability_score for r in self.results) / len(self.results)

                    if self.results

                    else 0

                ),

            },

        }

        return json.dumps(report_dict, indent=2, default=decimal_to_float)


class ParameterSweep:

    """Grid search across parameter space"""

    def __init__(

        self,

        strategy_func: Callable,

        strategy_name: str = "Strategy",

        parameter_config: Optional[ParameterConfig] = None,

    ):
        """

        Initialize parameter sweep.


        Args:

            strategy_func: Function that creates strategy with params dict

            strategy_name: Strategy name

            parameter_config: ParameterConfig with ranges

        """

        self.strategy_func = strategy_func

        self.strategy_name = strategy_name

        self.parameter_config = parameter_config or ParameterConfig.default_circuitbreaker_config()

        self.report: Optional[ParameterReport] = None

    def generate_parameter_sets(self) -> List[ParameterSet]:
        """Generate all parameter combinations"""

        param_names = list(self.parameter_config.parameters.keys())

        param_ranges = [

            self.parameter_config.parameters[name].generate_values() for name in param_names

        ]

        # Cartesian product

        from itertools import product

        combinations = list(product(*param_ranges))

        param_sets = []

        for idx, combination in enumerate(combinations):

            params = {name: value for name, value in zip(param_names, combination)}

            param_sets.append(ParameterSet(params, idx))

        return param_sets

    def run_sweep(

        self,

        df: pd.DataFrame,

        validation_engine: Any,  # ValidationEngine instance

        test_size_percent: float = 30.0,

    ) -> ParameterReport:
        """

        Run full parameter sweep.


        Args:

            df: OHLCV DataFrame

            validation_engine: ValidationEngine for validation

            test_size_percent: Test data percentage


        Returns:

            ParameterReport with results

        """

        from execution.backtest_runner import TrainTestSplitter

        start_time = datetime.now()

        # Generate all combinations

        param_sets = self.generate_parameter_sets()

        logger.info(f"Starting sweep: {len(param_sets)} combinations")

        # Split data once

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent)

        # Create report

        self.report = ParameterReport(

            strategy_name=self.strategy_name,

            parameter_config=self.parameter_config,

            total_combinations=len(param_sets),

        )

        # Run each parameter set

        for idx, param_set in enumerate(param_sets):

            if (idx + 1) % max(1, len(param_sets) // 10) == 0:

                logger.info(f"Progress: {idx + 1}/{len(param_sets)}")

            try:

                # Create strategy with these parameters

                self.strategy_func(param_set.to_dict())

                # Validate on train data

                train_metrics = validation_engine.validate_on_data(

                    train_df,

                    period_type="train",

                )

                # Validate on test data

                test_metrics = validation_engine.validate_on_data(

                    test_df,

                    period_type="test",

                )

                # Analyze stability

                stability = self._analyze_stability(train_metrics, test_metrics)

                # Create result

                result = ParameterResult(

                    param_set=param_set,

                    train_metrics=train_metrics,

                    test_metrics=test_metrics,

                    stability_score=stability.calculate_score(),

                    degradation_metrics={

                        "pnl_degradation_pct": stability.pnl_degradation_pct,

                        "win_rate_change_pct": stability.win_rate_change_pct,

                        "pf_change_pct": stability.pf_change_pct,

                        "dd_increase_pct": stability.dd_increase_pct,

                    },

                    warnings=stability.overfitting_signals,

                )

                self.report.add_result(result)

            except Exception as e:

                logger.warning(f"Failed for params {param_set.to_dict()}: {e}")

                continue

        # Get top stable

        self.report.get_top_stable(n=10)

        # Calculate duration

        self.report.sweep_duration_seconds = (datetime.now() - start_time).total_seconds()

        logger.info(f"Sweep complete in {self.report.sweep_duration_seconds:.1f}s")

        return self.report

    def _analyze_stability(

        self,

        train_metrics: Any,

        test_metrics: Any,

    ) -> StabilityMetrics:
        """Analyze stability between train and test periods"""

        stability = StabilityMetrics()

        if not train_metrics or not test_metrics:

            return stability

        # PnL degradation

        if train_metrics.net_pnl != 0:

            stability.pnl_degradation_pct = float(

                (test_metrics.net_pnl - train_metrics.net_pnl) / abs(train_metrics.net_pnl) * 100

            )

        # Win rate change

        stability.win_rate_change_pct = float(test_metrics.win_rate - train_metrics.win_rate)

        # Profit factor change

        if train_metrics.profit_factor != 0:

            stability.pf_change_pct = float(

                (test_metrics.profit_factor - train_metrics.profit_factor)

                / train_metrics.profit_factor

                * 100

            )

        # Drawdown increase

        if train_metrics.max_drawdown_percent != 0:

            stability.dd_increase_pct = float(

                test_metrics.max_drawdown_percent - train_metrics.max_drawdown_percent

            )

        # Expectancy consistency

        if train_metrics.expectancy != 0:

            stability.expectancy_consistency = float(

                test_metrics.expectancy / train_metrics.expectancy

            )

        # Trade ratio

        if train_metrics.total_trades > 0:

            stability.trades_ratio = float(test_metrics.total_trades) / float(

                train_metrics.total_trades

            )

        # Detect overfitting signals

        if stability.pnl_degradation_pct < -30:

            stability.overfitting_signals.append(

                f"Severe PnL degradation: {stability.pnl_degradation_pct:.1f}%"

            )

        if stability.win_rate_change_pct < -20:

            stability.overfitting_signals.append(

                f"Large win rate drop: {stability.win_rate_change_pct:.1f}%"

            )

        if stability.pf_change_pct < -30:

            stability.overfitting_signals.append(

                f"Profit factor drop: {stability.pf_change_pct:.1f}%"

            )

        if stability.dd_increase_pct > 10:

            stability.overfitting_signals.append(

                f"Drawdown increased: {stability.dd_increase_pct:.1f}%"

            )

        if 0.5 < stability.trades_ratio < 0.8:

            stability.overfitting_signals.append(

                f"Fewer trades on test data (ratio: {stability.trades_ratio:.2f})"

            )

        return stability
