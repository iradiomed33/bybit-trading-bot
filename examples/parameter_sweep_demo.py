"""

VAL-002 Parameter Sweep Example


Demonstrates:

1. Parameter range configuration

2. Grid search across ranges

3. Stability analysis (train vs test)

4. Top-10 stable parameter selection

"""


import pandas as pd

from decimal import Decimal

from typing import Dict


from validation.parameter_sweep import (

    ParameterConfig,

    ParameterSweep,

    ParameterRange,

    ParameterType,

)

from validation.validation_engine import ValidationEngine


class SimpleVMAStrategy:

    """Simple strategy with configurable MA period"""

    def __init__(self, params: Dict[str, float]):
        """Initialize with parameters"""

        self.ma_period = int(params.get("ma_period", 20))

        self.threshold_pct = params.get("threshold_pct", 0.5)

    def generate_signals(self, df: pd.DataFrame) -> Dict[int, Dict]:
        """Generate signals based on MA"""

        signals = {}

        df_copy = df.copy()

        df_copy["ma"] = df_copy["close"].rolling(window=self.ma_period).mean()

        position_open = False

        for i in range(self.ma_period, len(df_copy)):

            close = df_copy.iloc[i]["close"]

            ma = df_copy.iloc[i]["ma"]

            if pd.isna(ma):

                continue

            # Buy signal

            pct_above_ma = (close - ma) / ma * 100

            if not position_open and pct_above_ma > self.threshold_pct:

                signals[i] = {

                    "type": "long",

                    "symbol": "BTCUSDT",

                    "qty": Decimal("1"),

                }

                position_open = True

            # Sell signal

            elif position_open and pct_above_ma < -self.threshold_pct:

                signals[i] = {

                    "type": "close",

                    "symbol": "BTCUSDT",

                }

                position_open = False

        return signals


def generate_sample_data(num_candles: int = 200) -> pd.DataFrame:
    """Generate sample OHLCV data with trend"""

    import random

    timestamps = pd.date_range(start="2024-01-01", periods=num_candles, freq="1h")

    data = []

    current_price = 50000.0

    for ts in timestamps:

        # Slight uptrend

        random_change = random.gauss(0.0005, 0.01)

        current_price *= 1 + random_change

        data.append(

            {

                "timestamp": ts,

                "open": current_price * 0.998,

                "high": current_price * 1.005,

                "low": current_price * 0.995,

                "close": current_price,

                "volume": 100.0 + random.uniform(0, 50),

            }

        )

    return pd.DataFrame(data)


def main():
    """Run parameter sweep example"""

    print("=" * 80)

    print("VAL-002: Parameter Sweep with Stability Analysis")

    print("=" * 80)

    # 1. Generate data

    print("\n1. Generating sample data...")

    df = generate_sample_data(num_candles=200)

    print(f"   [OK] Generated {len(df)} candles")

    print(f"   [OK] Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # 2. Define parameter ranges

    print("\n2. Defining parameter ranges...")

    config = ParameterConfig()

    config.add_parameter(

        ParameterRange(

            name="ma_period",

            param_type=ParameterType.INTEGER,

            min_value=10,

            max_value=30,

            step=5,

            description="Moving Average period",

        )

    )

    config.add_parameter(

        ParameterRange(

            name="threshold_pct",

            param_type=ParameterType.FLOAT,

            min_value=0.2,

            max_value=1.0,

            step=0.2,

            description="Threshold % above/below MA",

        )

    )

    total_combos = config.get_total_combinations()

    print("   [OK] Parameter ranges defined")

    print(f"   [OK] Total combinations: {total_combos}")

    # 3. Create parameter sweep

    print("\n3. Running parameter sweep...")

    print(f"   (This may take a minute for {total_combos} combinations...)")

    def strategy_factory(params: Dict) -> object:
        """Factory function to create strategy with params"""

        return SimpleVMAStrategy(params)

    sweep = ParameterSweep(

        strategy_func=strategy_factory,

        strategy_name="SimpleVMAStrategy",

        parameter_config=config,

    )

    # Create validation engine

    engine = ValidationEngine(

        strategy_func=lambda df, p=None: None,  # Placeholder

        strategy_name="SimpleVMAStrategy",

    )

    # Run sweep

    report = sweep.run_sweep(df, engine, test_size_percent=30)

    print("   [OK] Sweep complete!")

    print(f"   [OK] Evaluated {len(report.results)} parameter combinations")

    print(f"   [OK] Duration: {report.sweep_duration_seconds:.1f}s")

    # 4. Display top stable parameters

    print("\n4. Top 10 Stable Parameter Sets:")

    print("   " + "-" * 76)

    if report.top_stable_params:

        for idx, result in enumerate(report.top_stable_params[:10], 1):

            params = result.param_set.to_dict()

            stability = result.stability_score

            degradation = result.degradation_metrics

            print(f"\n   [{idx}] Stability Score: {float(stability):.1f}/100")

            print("       Parameters:")

            for pname, pvalue in params.items():

                print(f"         - {pname}: {pvalue}")

            print("       Metrics:")

            print(

                f"         Train PF: {float(result.train_metrics.profit_factor):.2f}"

                if result.train_metrics

                else "         Train PF: N/A"

            )

            print(

                f"         Test PF:  {float(result.test_metrics.profit_factor):.2f}"

                if result.test_metrics

                else "         Test PF:  N/A"

            )

            print(f"         PnL Degradation: {degradation.get('pnl_degradation_pct', 0):.1f}%")

            print(f"         Win Rate Change: {degradation.get('win_rate_change_pct', 0):.1f}%")

            print(f"         Max DD Change:   {degradation.get('dd_increase_pct', 0):.1f}%")

            if result.warnings:

                print("       Warnings:")

                for warning in result.warnings:

                    print(f"         - {warning}")

    # 5. Stability statistics

    print("\n5. Stability Statistics:")

    print("   " + "-" * 76)

    min_score, max_score = report.get_stability_range()

    avg_score = (

        sum(r.stability_score for r in report.results) / len(report.results)

        if report.results

        else 0

    )

    print(f"   Min Stability Score: {float(min_score):.1f}/100")

    print(f"   Max Stability Score: {float(max_score):.1f}/100")

    print(f"   Avg Stability Score: {float(avg_score):.1f}/100")

    # 6. Parameter sensitivity analysis

    print("\n6. Parameter Sensitivity:")

    print("   " + "-" * 76)

    if report.results:

        # Group by ma_period

        by_ma = {}

        for result in report.results:

            ma = result.param_set.to_dict().get("ma_period")

            if ma not in by_ma:

                by_ma[ma] = []

            by_ma[ma].append(float(result.stability_score))

        print("   MA Period Impact:")

        for ma in sorted(by_ma.keys()):

            scores = by_ma[ma]

            avg = sum(scores) / len(scores)

            print(f"      MA {int(ma):2d}: Avg Stability = {avg:.1f} (n={len(scores)})")

    # 7. Export JSON report

    print("\n7. Exporting JSON report...")

    json_report = report.export_json()

    print("   [OK] Report exported")

    print("\n   JSON Summary:")

    print("   " + "-" * 76)

    import json

    report_dict = json.loads(json_report)

    print(f"   Strategy: {report_dict['strategy_name']}")

    print(f"   Total combinations: {report_dict['total_combinations']}")

    print(f"   Combinations evaluated: {report_dict['combinations_evaluated']}")

    print(f"   Duration: {report_dict['sweep_duration_seconds']:.1f}s")

    print("\n" + "=" * 80)

    print("VAL-002 Demo Complete!")

    print("=" * 80)

    return report


if __name__ == "__main__":

    report = main()
