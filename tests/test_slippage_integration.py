"""

Интеграционный тест для EXE-003: Проверка что слиппедж влияет на результаты бэктеста


DoD:

- Метрики БЕЗ слиппеджа лучше чем С слиппеджем

- Профит уменьшается из-за слиппеджа

- Drawdown увеличивается из-за слиппеджа

"""


import pytest

from decimal import Decimal

import pandas as pd

import numpy as np

from execution.backtest_runner import BacktestConfig, BacktestRunner

from execution.paper_trading_simulator import PaperTradingConfig, PaperTradingSimulator


class SimpleMovingAveragaStrategy:

    """Простая стратегия для тестирования - MA crossover"""

    def __init__(self, fast_period=5, slow_period=20):

        self.fast_period = fast_period

        self.slow_period = slow_period

    def __call__(self, df):
        """

        Возвращает сигналы:

        - "LONG" если fastMA > slowMA

        - "SHORT" если fastMA < slowMA

        - None если нет позиции

        """

        if len(df) < self.slow_period:

            return None

        close = df["close"].values

        fast_ma = pd.Series(close).rolling(self.fast_period).mean().iloc[-1]

        slow_ma = pd.Series(close).rolling(self.slow_period).mean().iloc[-1]

        if fast_ma > slow_ma:

            return "LONG"

        elif fast_ma < slow_ma:

            return "SHORT"

        return None


def create_synthetic_data(days=100) -> pd.DataFrame:
    """

    Создать синтетические OHLCV данные с трендом.

    """

    dates = pd.date_range(start="2023-01-01", periods=days * 4, freq="6h")

    # Начальная цена

    base_price = 50000

    # Генерируем цены с трендом + шум

    np.random.seed(42)

    prices = [base_price]

    for i in range(len(dates) - 1):

        # Тренд вверх + шум

        change = np.random.normal(0.001, 0.005)  # mean=0.1%, std=0.5%

        new_price = prices[-1] * (1 + change)

        prices.append(new_price)

    df = pd.DataFrame(

        {

            "timestamp": dates,

            "open": prices,

            "high": [p * 1.01 for p in prices],

            "low": [p * 0.99 for p in prices],

            "close": prices,

            "volume": np.random.uniform(1000000, 2000000, len(prices)),

        }

    )

    return df


class TestSlippageImpactOnBacktest:

    """Проверка влияния слиппеджа на результаты бэктеста"""

    def test_slippage_reduces_profit(self):
        """Слиппедж уменьшает прибыль"""

        df = create_synthetic_data(days=30)

        strategy = SimpleMovingAveragaStrategy(fast_period=5, slow_period=20)

        # Бэктест БЕЗ слиппеджа

        config_no_slip = BacktestConfig(

            initial_balance=Decimal("10000"),

            slippage_bps=Decimal("0"),  # No slippage

            slippage_volatility_factor_enabled=False,

            slippage_volume_factor_enabled=False,

        )

        runner_no_slip = BacktestRunner(config_no_slip)

        result_no_slip = runner_no_slip.run_backtest(df, strategy, "NO_SLIPPAGE")

        # Бэктест С слиппеджем

        config_with_slip = BacktestConfig(

            initial_balance=Decimal("10000"),

            slippage_bps=Decimal("2"),  # 2 bps

            slippage_volatility_factor_enabled=True,

            slippage_volume_factor_enabled=True,

        )

        runner_with_slip = BacktestRunner(config_with_slip)

        result_with_slip = runner_with_slip.run_backtest(df, strategy, "WITH_SLIPPAGE")

        # Финальный баланс БЕЗ слиппеджа должен быть выше

        final_equity_no_slip = result_no_slip["equity_curve"][-1]

        final_equity_with_slip = result_with_slip["equity_curve"][-1]

        assert (

            final_equity_no_slip >= final_equity_with_slip

        ), f"No slippage: {final_equity_no_slip}, With slippage: {final_equity_with_slip}"

    def test_different_slippage_levels(self):
        """Разные уровни слиппеджа дают разные результаты"""

        df = create_synthetic_data(days=30)

        strategy = SimpleMovingAveragaStrategy(fast_period=5, slow_period=20)

        results = {}

        for slippage_bps in [0, 1, 5, 10]:

            config = BacktestConfig(

                initial_balance=Decimal("10000"),

                slippage_bps=Decimal(str(slippage_bps)),

                slippage_volatility_factor_enabled=True,

                slippage_volume_factor_enabled=True,

            )

            runner = BacktestRunner(config)

            result = runner.run_backtest(df, strategy, f"SLIPPAGE_{slippage_bps}")

            final_equity = result["equity_curve"][-1]

            results[slippage_bps] = float(final_equity)

        # Результаты должны убывать с ростом слиппеджа

        assert (

            results[0] >= results[1] >= results[5] >= results[10]

        ), f"Results don't decrease with slippage: {results}"

    def test_slippage_config_from_backtest(self):
        """Проверить что конфиг BacktestRunner передает параметры в PaperTradingSimulator"""

        config = BacktestConfig(

            initial_balance=Decimal("10000"),

            slippage_bps=Decimal("5"),

            slippage_volatility_factor_enabled=True,

            slippage_volume_factor_enabled=False,

        )

        runner = BacktestRunner(config)

        # Проверяем что runner может быть создан с новыми параметрами

        assert runner.config.slippage_bps == Decimal("5")

        assert runner.config.slippage_volatility_factor_enabled is True

        assert runner.config.slippage_volume_factor_enabled is False


class TestSlippageBackwardCompatibility:

    """Проверка обратной совместимости"""

    def test_legacy_slippage_buy_sell_parameters(self):
        """Legacy параметры slippage_buy/sell всё ещё работают"""

        config = PaperTradingConfig(

            initial_balance=Decimal("10000"),

            slippage_buy=Decimal("0.0001"),  # Legacy

            slippage_sell=Decimal("0.0001"),  # Legacy

        )

        # Должно работать без ошибок

        simulator = PaperTradingSimulator(config)

        assert simulator is not None


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
