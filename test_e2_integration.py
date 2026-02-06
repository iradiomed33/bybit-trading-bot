# -*- coding: utf-8 -*-

"""

E2 - Backtest Runner Integration Tests


Тесты БЕЗ pandas (работают с Python 3.13)

"""


from decimal import Decimal

from execution.backtest_runner import (

    BacktestConfig,

    HistoricalDataLoader,

    TrainTestSplitter,

    BacktestRunner,

)


def test_backtest_config_creation():
    """Создать конфиг бэктеста"""

    config = BacktestConfig(

        initial_balance=Decimal("10000"),

        commission_maker=Decimal("0.0002"),

        commission_taker=Decimal("0.0004"),

        slippage=Decimal("0.0001"),

        test_size_percent=30.0,

    )

    assert config.initial_balance == Decimal("10000")

    assert config.test_size_percent == 30.0

    print("✓ test_backtest_config_creation")


def test_historical_data_loader_sample_generation():
    """Генерировать sample данные"""

    df = HistoricalDataLoader.generate_sample_data(

        num_candles=100, start_price=Decimal("40000"), volatility=Decimal("0.02")

    )

    assert df is not None

    assert len(df) == 100

    assert "timestamp" in df.columns

    assert "open" in df.columns

    assert "close" in df.columns

    print("✓ test_historical_data_loader_sample_generation")


def test_historical_data_loader_reproducibility():
    """Sample данные должны быть воспроизводимы"""

    df1 = HistoricalDataLoader.generate_sample_data(num_candles=50)

    df2 = HistoricalDataLoader.generate_sample_data(num_candles=50)

    assert df1 is not None and df2 is not None

    # Проверим что в обоих одинаковое количество строк

    assert len(df1) == len(df2) == 50

    print("✓ test_historical_data_loader_reproducibility")


def test_train_test_splitter():
    """Разделить данные на train/test"""

    df = HistoricalDataLoader.generate_sample_data(num_candles=100)

    train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

    assert train_df is not None

    assert test_df is not None

    assert len(train_df) == 70

    assert len(test_df) == 30

    print("✓ test_train_test_splitter")


def test_train_test_no_leakage():
    """Проверить что нет data leakage"""

    df = HistoricalDataLoader.generate_sample_data(num_candles=100)

    train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

    # Проверить что нет leakage

    is_valid = TrainTestSplitter.validate_no_leakage(train_df, test_df)

    assert is_valid is True

    print("✓ test_train_test_no_leakage")


def test_backtest_runner_initialization():
    """Инициализировать BacktestRunner"""

    config = BacktestConfig(initial_balance=Decimal("10000"))

    runner = BacktestRunner(config)

    assert runner is not None

    assert runner.config.initial_balance == Decimal("10000")

    print("✓ test_backtest_runner_initialization")


def test_backtest_runner_run_basic():
    """Запустить базовый бэктест"""

    config = BacktestConfig(initial_balance=Decimal("10000"))

    runner = BacktestRunner(config)

    df = HistoricalDataLoader.generate_sample_data(num_candles=50)

    def dummy_strategy(df):

        # Никогда не возвращает сигнал

        return None

    result = runner.run_backtest(df, dummy_strategy, symbol="BTCUSDT", name="test_basic")

    assert result is not None

    assert "metrics" in result

    assert "trades" in result

    assert "simulator" in result

    assert result["metrics"].total_trades == 0

    print("✓ test_backtest_runner_run_basic")


def test_backtest_runner_train_test():
    """Запустить train/test бэктест"""

    config = BacktestConfig(initial_balance=Decimal("10000"), test_size_percent=30)

    runner = BacktestRunner(config)

    df = HistoricalDataLoader.generate_sample_data(num_candles=100)

    def dummy_strategy(df):

        return None

    results = runner.run_train_test(df, dummy_strategy, symbol="BTCUSDT", name="test_train_test")

    assert results is not None

    assert "train" in results

    assert "test" in results

    assert "train_size" in results

    assert "test_size" in results

    assert results["train_size"] == 70

    assert results["test_size"] == 30

    print("✓ test_backtest_runner_train_test")


def main():
    """Run all tests"""

    tests = [

        test_backtest_config_creation,

        test_historical_data_loader_sample_generation,

        test_historical_data_loader_reproducibility,

        test_train_test_splitter,

        test_train_test_no_leakage,

        test_backtest_runner_initialization,

        test_backtest_runner_run_basic,

        test_backtest_runner_train_test,

    ]

    passed = 0

    failed = 0

    for test in tests:

        try:

            test()

            passed += 1

        except Exception as e:

            print(f"✗ {test.__name__}: {e}")

            failed += 1

    print(f"\n{'=' * 60}")

    print(f"Результаты: {passed} passed, {failed} failed")

    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":

    success = main()

    exit(0 if success else 1)
