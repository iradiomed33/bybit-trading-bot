# -*- coding: utf-8 -*-

"""

Tests for Backtest Runner - E2 EPIC


Тестируем:

- HistoricalDataLoader (CSV, sample generation)

- TrainTestSplitter (time-based split, no leakage)

- BacktestRunner (single backtest, train/test workflow)

- BacktestMetricsReporter (comparison, export)

"""


import pytest

import pandas as pd

from decimal import Decimal

import json

import tempfile

import os


from execution.backtest_runner import (

    BacktestConfig,

    HistoricalDataLoader,

    TrainTestSplitter,

    BacktestRunner,

)

from execution.backtest_reporter import BacktestMetricsReporter


class TestHistoricalDataLoader:

    """Тесты для загрузки исторических данных"""

    def test_generate_sample_data_default(self):
        """Сгенерировать данные по умолчанию"""

        df = HistoricalDataLoader.generate_sample_data()

        assert len(df) == 1000

        assert "timestamp" in df.columns  # Исправлено: timestamp вместо time

        assert "open" in df.columns

        assert "high" in df.columns

        assert "low" in df.columns

        assert "close" in df.columns

        assert "volume" in df.columns

        # Проверить, что данные валидны

        assert all(df["high"] >= df["low"])

        assert all(df["close"] >= df["low"])

        assert all(df["close"] <= df["high"])

        assert all(df["volume"] > 0)

    def test_generate_sample_data_custom(self):
        """Сгенерировать данные с кастомными параметрами"""

        df = HistoricalDataLoader.generate_sample_data(

            num_candles=100, start_price=Decimal("50000"), volatility=0.05

        )

        assert len(df) == 100

        assert df["close"].iloc[0] > 0

    def test_generate_sample_data_reproducible(self):
        """Генерация должна быть воспроизводима (seed=42)"""

        df1 = HistoricalDataLoader.generate_sample_data()

        df2 = HistoricalDataLoader.generate_sample_data()

        # Должны быть одинаковые (same seed)

        pd.testing.assert_frame_equal(df1, df2)

    def test_load_from_csv_creates_file(self):
        """Загрузить данные из CSV"""

        # Создать временный CSV

        df_original = HistoricalDataLoader.generate_sample_data(num_candles=50)

        with tempfile.TemporaryDirectory() as tmpdir:

            csv_path = os.path.join(tmpdir, "test_data.csv")

            df_original.to_csv(csv_path, index=False)

            # Загрузить

            df_loaded = HistoricalDataLoader.load_from_csv(csv_path)

            assert len(df_loaded) == 50

            assert list(df_loaded.columns) == list(df_original.columns)

    def test_load_from_csv_invalid_path(self):
        """Невалидный путь должен вызвать ошибку"""

        with pytest.raises(FileNotFoundError):

            HistoricalDataLoader.load_from_csv("/invalid/path.csv")


class TestTrainTestSplitter:

    """Тесты для разделения train/test"""

    def test_split_basic(self):
        """Базовое разделение 70/30"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

        assert len(train_df) == 700

        assert len(test_df) == 300

        assert len(train_df) + len(test_df) == 1000

    def test_split_custom_percent(self):
        """Разделение с кастомным процентом"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=20)

        assert len(train_df) == 800

        assert len(test_df) == 200

    def test_split_chronological_order(self):
        """Train должен быть ДО test (no data leakage)"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

        # Проверить, что test идет после train

        train_max_time = train_df["timestamp"].max()

        test_min_time = test_df["timestamp"].min()

        assert test_min_time >= train_max_time

    def test_validate_no_leakage_valid(self):
        """Валидное разделение не должно вызвать ошибку"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

        # Должно вернуть True

        is_valid = TrainTestSplitter.validate_no_leakage(train_df, test_df)

        assert is_valid is True

    def test_validate_no_leakage_invalid(self):
        """Если test раньше train, должна вернуть False"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

        # Поменять местами - должна вернуть False (есть leakage)

        is_valid = TrainTestSplitter.validate_no_leakage(test_df, train_df)

        assert is_valid is False

    def test_split_preserves_data(self):
        """Разделение должно сохранить все данные"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=1000)

        train_df, test_df = TrainTestSplitter.split(df, test_size_percent=30)

        # Объединить обратно и сравнить

        combined = pd.concat([train_df, test_df], ignore_index=True)

        # Сортировать по timestamp и сбросить индекс для сравнения

        combined_sorted = combined.sort_values("timestamp").reset_index(drop=True)

        df_sorted = df.sort_values("timestamp").reset_index(drop=True)

        pd.testing.assert_frame_equal(combined_sorted, df_sorted)


class TestBacktestRunner:

    """Тесты для BacktestRunner"""

    @staticmethod
    def simple_strategy(df):
        """Простая стратегия для тестирования: покупай когда close > open"""

        if len(df) < 1:

            return None

        latest = df.iloc[-1]

        # Signal только на первой свече или при смене тренда

        if latest["close"] > latest["open"]:

            # Uptrend - покупай

            return {

                "side": "BUY",

                "qty": Decimal("0.1"),

                "stop_loss_price": Decimal(str(latest["low"])) * Decimal("0.95"),

                "take_profit_price": Decimal(str(latest["high"])) * Decimal("1.05"),

            }

        return None

    def test_run_backtest_basic(self):
        """Базовый бэктест"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=100)

        config = BacktestConfig(

            initial_balance=Decimal("10000"),

            commission_maker=Decimal("0.0002"),

            commission_taker=Decimal("0.0004"),

            slippage_bps=Decimal("1"),  # 1 bps = 0.0001

        )

        runner = BacktestRunner(config)

        result = runner.run_backtest(df, self.simple_strategy, symbol="BTCUSDT", name="test_simple")

        assert "simulator" in result

        assert "trades" in result

        assert "metrics" in result

        assert "equity_curve" in result

        assert "start_date" in result

        assert "end_date" in result

    def test_run_backtest_no_trades(self):
        """Бэктест без сделок (всегда возвращает None)"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=50)

        config = BacktestConfig(initial_balance=Decimal("10000"))

        runner = BacktestRunner(config)

        def no_trade_strategy(df):

            return None

        result = runner.run_backtest(df, no_trade_strategy, symbol="BTCUSDT", name="no_trades")

        assert len(result["trades"]) == 0

        assert result["metrics"].total_trades == 0

    def test_run_backtest_equity_tracking(self):
        """Equity curve должна быть записана"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=100)

        config = BacktestConfig(initial_balance=Decimal("10000"))

        runner = BacktestRunner(config)

        result = runner.run_backtest(df, self.simple_strategy, symbol="BTCUSDT", name="test_equity")

        assert len(result["equity_curve"]) > 0

        # Первое значение должно быть близко к начальному балансу (может отличаться из-за начальных операций)

        first_equity = result["equity_curve"][0]

        assert float(first_equity) > 9900  # Примерно 10000, но может быть меньше из-за комиссий

    def test_run_train_test_split(self):
        """Запустить train/test разделение"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=200)

        config = BacktestConfig(

            initial_balance=Decimal("10000"),

            test_size_percent=30,

        )

        runner = BacktestRunner(config)

        results = runner.run_train_test(

            df, self.simple_strategy, symbol="BTCUSDT", name="test_train_test"

        )

        assert "train" in results

        assert "test" in results

        assert "train_size" in results

        assert "test_size" in results

        assert results["train_size"] == 140  # 70%

        assert results["test_size"] == 60  # 30%

    def test_run_train_test_metrics_consistency(self):
        """Метрики должны быть consistent в train/test"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=200)

        config = BacktestConfig(

            initial_balance=Decimal("10000"),

            test_size_percent=30,

        )

        runner = BacktestRunner(config)

        results = runner.run_train_test(

            df, self.simple_strategy, symbol="BTCUSDT", name="test_metrics"

        )

        # Оба должны быть запущены

        assert results["train"]["metrics"] is not None

        assert results["test"]["metrics"] is not None

        # Меньше тестовых trades, чем обучающих (обычно)

        # или равно (может быть везение)

        assert (

            results["test"]["metrics"].total_trades <= results["train"]["metrics"].total_trades * 2

        )

    def test_run_backtest_result_structure(self):
        """Проверить структуру результата"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=50)

        config = BacktestConfig(initial_balance=Decimal("10000"))

        runner = BacktestRunner(config)

        result = runner.run_backtest(

            df, self.simple_strategy, symbol="BTCUSDT", name="test_structure"

        )

        # Обязательные ключи

        required_keys = {

            "name",

            "symbol",

            "start_date",

            "end_date",

            "candles_count",

            "start_price",

            "end_price",

            "trades_count",

            "simulator",

            "trades",

            "metrics",

            "equity_curve",

        }

        assert all(key in result for key in required_keys)


class TestBacktestMetricsReporter:

    """Тесты для reporter"""

    @staticmethod
    def get_sample_result():
        """Получить sample result для тестов"""

        df = HistoricalDataLoader.generate_sample_data(num_candles=50)

        config = BacktestConfig(initial_balance=Decimal("10000"))

        runner = BacktestRunner(config)

        def simple_strategy(df):

            if len(df) < 1:

                return None

            if df.iloc[-1]["close"] > df.iloc[-1]["open"]:

                return {

                    "side": "BUY",

                    "qty": Decimal("0.01"),

                    "stop_loss_price": Decimal(str(df.iloc[-1]["low"])) * Decimal("0.95"),

                    "take_profit_price": Decimal(str(df.iloc[-1]["high"])) * Decimal("1.05"),

                }

            return None

        return runner.run_backtest(df, simple_strategy, symbol="BTCUSDT", name="test")

    def test_format_metrics_table(self):
        """Форматировать metrics в таблицу"""

        result = self.get_sample_result()

        df = BacktestMetricsReporter.format_metrics_table(result)

        assert isinstance(df, pd.DataFrame)

        assert len(df) == 17  # 17 метрик

        assert "Metric" in df.columns

        assert "Value" in df.columns

    def test_compare_strategies(self):
        """Сравнить несколько стратегий"""

        result1 = self.get_sample_result()

        result2 = self.get_sample_result()

        results = {

            "strategy_1": result1,

            "strategy_2": result2,

        }

        df = BacktestMetricsReporter.compare_strategies(results)

        assert isinstance(df, pd.DataFrame)

        assert len(df) == 2

        assert "Strategy" in df.columns

        assert "Trades" in df.columns

    def test_compare_train_test(self):
        """Сравнить train vs test"""

        config = BacktestConfig(initial_balance=Decimal("10000"))

        runner = BacktestRunner(config)

        df = HistoricalDataLoader.generate_sample_data(num_candles=100)

        def dummy_strategy(df):

            if len(df) < 1:

                return None

            if df.iloc[-1]["close"] > df.iloc[-1]["open"]:

                return {

                    "side": "BUY",

                    "qty": Decimal("0.01"),

                    "stop_loss_price": Decimal(str(df.iloc[-1]["low"])) * Decimal("0.95"),

                    "take_profit_price": Decimal(str(df.iloc[-1]["high"])) * Decimal("1.05"),

                }

            return None

        results = runner.run_train_test(df, dummy_strategy, "BTCUSDT", "test")

        comparison = BacktestMetricsReporter.compare_train_test(results["train"], results["test"])

        assert isinstance(comparison, pd.DataFrame)

        assert "Train" in comparison.columns

        assert "Test" in comparison.columns

    def test_export_to_json(self):
        """Экспортировать в JSON"""

        result = self.get_sample_result()

        with tempfile.TemporaryDirectory() as tmpdir:

            json_path = os.path.join(tmpdir, "results.json")

            json_str = BacktestMetricsReporter.export_to_json(result, json_path)

            # Проверить, что файл создан

            assert os.path.exists(json_path)

            # Прочитать и проверить структуру

            with open(json_path) as f:

                data = json.load(f)

            assert "metrics" in data

            assert "trades" in data

            assert "name" in data

    def test_generate_html_report(self):
        """Генерировать HTML отчет"""

        result = self.get_sample_result()

        results = {"test": result}

        with tempfile.TemporaryDirectory() as tmpdir:

            html_path = os.path.join(tmpdir, "report.html")

            html = BacktestMetricsReporter.generate_html_report(results, html_path)

            assert os.path.exists(html_path)

            assert "<html>" in html.lower() or "<!doctype" in html.lower()

            # Проверяем что есть какие-то таблицы или данные в отчёте

            assert len(html) > 100

    def test_print_summary(self, capsys):
        """Напечатать summary"""

        result = self.get_sample_result()

        BacktestMetricsReporter.print_summary(result)

        captured = capsys.readouterr()

        assert "Backtest" in captured.out

        assert "Total Trades" in captured.out


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
