"""

VAL-001 Sample Strategy Validation


Demonstrates:

1. Unified validation pipeline

2. Identical logic across train/test periods

3. Transparent fee reporting

4. Out-of-sample validation

"""


import pandas as pd

from decimal import Decimal

from typing import Dict


from execution.backtest_runner import BacktestRunner, BacktestConfig

from validation.validation_engine import ValidationEngine


class SimpleTrendStrategy:

    """Simple trend-following strategy"""

    def __init__(self, ma_period: int = 20):
        """

        Initialize strategy.


        Args:

            ma_period: Moving average period

        """

        self.ma_period = ma_period

    def generate_signals(self, df: pd.DataFrame) -> Dict[int, Dict]:
        """

        Generate trade signals.


        Args:

            df: OHLCV DataFrame


        Returns:

            Dict with index -> signal

        """

        signals = {}

        # Calculate MA

        df_copy = df.copy()

        df_copy["ma"] = df_copy["close"].rolling(window=self.ma_period).mean()

        position_open = False

        for i in range(self.ma_period, len(df_copy)):

            close = df_copy.iloc[i]["close"]

            ma = df_copy.iloc[i]["ma"]

            # Buy signal: price crosses above MA

            if not position_open and close > ma:

                signals[i] = {

                    "type": "long",

                    "symbol": "BTCUSDT",

                    "qty": Decimal("1"),

                    "comment": f"Price {close} > MA {ma}",

                }

                position_open = True

            # Sell signal: price crosses below MA

            elif position_open and close < ma:

                signals[i] = {

                    "type": "close",

                    "symbol": "BTCUSDT",

                    "comment": f"Price {close} < MA {ma}",

                }

                position_open = True

        return signals


def generate_sample_data(

    num_candles: int = 100,

    start_price: float = 50000.0,

    trend: float = 0.001,

    volatility: float = 0.02,

) -> pd.DataFrame:
    """

    Generate sample OHLCV data.


    Args:

        num_candles: Number of candles

        start_price: Starting price

        trend: Daily trend (0.001 = +0.1%)

        volatility: Volatility (0.02 = 2%)


    Returns:

        DataFrame with OHLCV data

    """

    import random

    timestamps = pd.date_range(start="2024-01-01", periods=num_candles, freq="1h")

    data = []

    current_price = start_price

    for ts in timestamps:

        # Apply trend and noise

        random_change = random.gauss(trend, volatility)

        current_price *= 1 + random_change

        # Generate OHLCV

        open_price = current_price * 0.998

        close_price = current_price

        high_price = current_price * 1.005

        low_price = current_price * 0.995

        volume = 100.0 + random.uniform(0, 50)

        data.append(

            {

                "timestamp": ts,

                "open": open_price,

                "high": high_price,

                "low": low_price,

                "close": close_price,

                "volume": volume,

            }

        )

    return pd.DataFrame(data)


def main():
    """Main function for VAL-001 demonstration"""

    print("=" * 80)

    print("VAL-001: Unified Validation Pipeline Demo")

    print("=" * 80)

    # Generate sample data

    print("\n1. Generating sample OHLCV data...")

    df = generate_sample_data(num_candles=100, trend=0.001, volatility=0.02)

    print(

        f"   [OK] Generated {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}"

    )

    print(f"   [OK] Price: ${df['open'].iloc[0]:.2f} -> ${df['close'].iloc[-1]:.2f}")

    # Initialize strategy

    print("\n2. Initializing SimpleTrendStrategy...")

    strategy = SimpleTrendStrategy(ma_period=20)

    print("   [OK] Strategy initialized with MA period=20")

    # Run unified validation

    print("\n3. Running unified VAL-001 validation pipeline...")

    config = BacktestConfig(

        initial_balance=Decimal("10000"),

        commission_maker=Decimal("0.0002"),

        commission_taker=Decimal("0.0004"),

        slippage_bps=Decimal("2"),

    )

    runner = BacktestRunner(config)

    # Run validation

    report = runner.run_unified_validation(

        df=df,

        strategy_func=strategy.generate_signals,

        strategy_name="SimpleTrendStrategy",

        config={"initial_balance": "10000"},

    )

    # Output results

    print("\n4. Validation Results:")

    print("   " + "-" * 76)

    if report.train_metrics:

        print("\n   TRAIN Period:")

        print(f"      Total trades: {report.train_metrics.total_trades}")

        print(f"      Winning trades: {report.train_metrics.winning_trades}")

        print(f"      Losing trades: {report.train_metrics.losing_trades}")

        print(f"      Gross PnL: ${float(report.train_metrics.gross_pnl):.2f}")

        print(f"      Net PnL: ${float(report.train_metrics.net_pnl):.2f}")

        print(f"      Win Rate: {float(report.train_metrics.win_rate):.1f}%")

        print(f"      Profit Factor: {float(report.train_metrics.profit_factor):.2f}")

        print(f"      Expectancy: ${float(report.train_metrics.expectancy):.2f}/trade")

        print(

            f"      Max Drawdown: ${float(report.train_metrics.max_drawdown_usd):.2f} ({float(report.train_metrics.max_drawdown_percent):.1f}%)"

        )

        print(f"      Total Commission: ${float(report.train_metrics.total_commission):.2f}")

        print(f"      Total Slippage: ${float(report.train_metrics.total_slippage):.2f}")

    if report.test_metrics:

        print("\n   TEST Period (Out-of-Sample):")

        print(f"      Total trades: {report.test_metrics.total_trades}")

        print(f"      Winning trades: {report.test_metrics.winning_trades}")

        print(f"      Losing trades: {report.test_metrics.losing_trades}")

        print(f"      Gross PnL: ${float(report.test_metrics.gross_pnl):.2f}")

        print(f"      Net PnL: ${float(report.test_metrics.net_pnl):.2f}")

        print(f"      Win Rate: {float(report.test_metrics.win_rate):.1f}%")

        print(f"      Profit Factor: {float(report.test_metrics.profit_factor):.2f}")

        print(f"      Expectancy: ${float(report.test_metrics.expectancy):.2f}/trade")

        print(

            f"      Max Drawdown: ${float(report.test_metrics.max_drawdown_usd):.2f} ({float(report.test_metrics.max_drawdown_percent):.1f}%)"

        )

        print(f"      Total Commission: ${float(report.test_metrics.total_commission):.2f}")

        print(f"      Total Slippage: ${float(report.test_metrics.total_slippage):.2f}")

    # Output train vs test comparison

    if report.train_vs_test:

        print("\n   TRAIN vs TEST Comparison:")

        comparison = report.train_vs_test

        print(

            f"      Trades: Train={comparison['trades']['train']}, Test={comparison['trades']['test']}"

        )

        print(

            f"      Net PnL: Train=${comparison['net_pnl']['train']:.2f}, Test=${comparison['net_pnl']['test']:.2f}"

        )

        print(

            f"      Win Rate: Train={comparison['win_rate']['train']:.1f}%, Test={comparison['win_rate']['test']:.1f}%"

        )

        print(

            f"      Profit Factor: Train={comparison['profit_factor']['train']:.2f}, Test={comparison['profit_factor']['test']:.2f}"

        )

        max_dd_key = "max_drawdown_pct" if "max_drawdown_pct" in comparison else "max_dd_percent"

        if max_dd_key in comparison:

            print(

                f"      Max DD%: Train={comparison[max_dd_key]['train']:.1f}%, Test={comparison[max_dd_key]['test']:.1f}%"

            )

        if "pnl_degradation_pct" in comparison:

            degradation = comparison["pnl_degradation_pct"]

            print(f"      PnL Degradation: {degradation:.1f}%")

    # Validation status

    print("\n   " + "-" * 76)

    if report.is_valid:

        print("   [OK] VALIDATION PASSED")

    else:

        print("   [FAILED] VALIDATION FAILED")

    if report.warnings:

        print("\n   Warnings:")

        for warning in report.warnings:

            print(f"      WARNING: {warning}")

    if report.errors:

        print("\n   Errors:")

        for error in report.errors:

            print(f"      ERROR: {error}")

    # Export JSON report

    print("\n5. Exporting JSON report...")

    json_report = runner.run_unified_validation(

        df=df,

        strategy_func=strategy.generate_signals,

        strategy_name="SimpleTrendStrategy",

    )

    engine = ValidationEngine(

        strategy_func=strategy.generate_signals,

        strategy_name="SimpleTrendStrategy",

    )

    json_output = engine.export_report(report)

    print("   [OK] Report exported")

    print("\n   JSON Output:")

    print("   " + "-" * 76)

    for line in json_output.split("\n"):

        print(f"   {line}")

    print("\n" + "=" * 80)

    print("Demo Complete!")

    print("=" * 80)


if __name__ == "__main__":

    main()
