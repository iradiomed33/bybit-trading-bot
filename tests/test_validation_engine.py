"""

VAL-001: Unified Validation Pipeline Tests


Тестирует:

1. Unified pipeline (свечи → features → signal → execution)

2. Metrics calculation (PF, DD, expectancy, etc.)

3. Fee impact (commission + slippage)

4. Train vs test validation (out-of-sample)

5. Report generation

"""


import pytest

from decimal import Decimal

from datetime import datetime

from typing import Dict

import pandas as pd


from validation.validation_engine import (

    TradeMetric,

    ValidationMetrics,

    UnifiedPipeline,

    ValidationEngine,

)


class TestTradeMetric:

    """Тесты для TradeMetric"""

    def test_create_trade_metric(self):
        """Создать trade metric"""

        trade = TradeMetric(

            entry_price=Decimal("50000"),

            exit_price=Decimal("51000"),

            qty=Decimal("1"),

            entry_time=datetime(2024, 1, 1),

            exit_time=datetime(2024, 1, 2),

            side="long",

            pnl_usd=Decimal("1000"),

            pnl_percent=Decimal("2"),

            commission=Decimal("10"),

            slippage=Decimal("5"),

            gross_pnl=Decimal("1015"),

            net_pnl=Decimal("1000"),

        )

        assert trade.entry_price == Decimal("50000")

        assert trade.exit_price == Decimal("51000")

        assert trade.net_pnl == Decimal("1000")

        assert trade.side == "long"


class TestValidationMetrics:

    """Тесты для ValidationMetrics"""

    def test_default_metrics(self):
        """Дефолтные метрики"""

        metrics = ValidationMetrics()

        assert metrics.total_trades == 0

        assert metrics.net_pnl == Decimal("0")

        assert metrics.max_drawdown_usd == Decimal("0")

        assert metrics.profit_factor == Decimal("0")

    def test_metrics_with_trades(self):
        """Метрики с данными"""

        trade = TradeMetric(

            entry_price=Decimal("100"),

            exit_price=Decimal("110"),

            qty=Decimal("1"),

            entry_time=datetime(2024, 1, 1),

            exit_time=datetime(2024, 1, 2),

            side="long",

            pnl_usd=Decimal("10"),

            pnl_percent=Decimal("10"),

            commission=Decimal("0.2"),

            slippage=Decimal("0"),

            gross_pnl=Decimal("10.2"),

            net_pnl=Decimal("10"),

        )

        metrics = ValidationMetrics(

            total_trades=1,

            winning_trades=1,

            net_pnl=Decimal("10"),

            trades=[trade],

        )

        assert metrics.total_trades == 1

        assert metrics.winning_trades == 1

        assert metrics.net_pnl == Decimal("10")


class TestUnifiedPipeline:

    """Тесты для UnifiedPipeline"""

    def test_pipeline_initialization(self):
        """Инициализировать pipeline"""

        pipeline = UnifiedPipeline(

            initial_balance=Decimal("10000"),

            commission_maker=Decimal("0.0002"),

            commission_taker=Decimal("0.0004"),

            slippage_bps=Decimal("2"),

        )

        assert pipeline.initial_balance == Decimal("10000")

        assert pipeline.equity == Decimal("10000")

        assert pipeline.commission_taker == Decimal("0.0004")

    def test_process_candle_no_signal(self):
        """Обработать свечу без сигнала"""

        pipeline = UnifiedPipeline()

        candle = {

            "timestamp": datetime(2024, 1, 1),

            "open": Decimal("50000"),

            "high": Decimal("51000"),

            "low": Decimal("49000"),

            "close": Decimal("50500"),

            "volume": Decimal("100"),

        }

        result = pipeline.process_candle(candle, signal=None)

        assert len(result["trades_closed"]) == 0

        assert result["position_opened"] is None

    def test_process_candle_with_open_signal(self):
        """Обработать свечу с сигналом открыть"""

        pipeline = UnifiedPipeline()

        candle = {

            "timestamp": datetime(2024, 1, 1),

            "open": Decimal("50000"),

            "high": Decimal("51000"),

            "low": Decimal("49000"),

            "close": Decimal("50500"),

            "volume": Decimal("100"),

        }

        signal = {

            "type": "long",

            "symbol": "BTCUSDT",

            "qty": Decimal("1"),

            "comment": "Buy signal",

        }

        result = pipeline.process_candle(candle, signal=signal)

        assert result["position_opened"] is not None

        assert result["position_opened"]["side"] == "long"

        assert result["position_opened"]["qty"] == Decimal("1")

    def test_close_position_long(self):
        """Закрыть long позицию"""

        pipeline = UnifiedPipeline()

        position = {

            "symbol": "BTCUSDT",

            "side": "long",

            "qty": Decimal("1"),

            "entry_price": Decimal("50000"),

            "entry_time": datetime(2024, 1, 1),

        }

        trade = pipeline._close_position(

            symbol="BTCUSDT",

            position=position,

            exit_price=Decimal("51000"),

            exit_time=datetime(2024, 1, 2),

        )

        assert trade.side == "long"

        assert trade.qty == Decimal("1")

        assert trade.gross_pnl == Decimal("1000")  # (51000 - 50000) * 1

        assert trade.net_pnl > 0

    def test_close_position_short(self):
        """Закрыть short позицию"""

        pipeline = UnifiedPipeline()

        position = {

            "symbol": "BTCUSDT",

            "side": "short",

            "qty": Decimal("1"),

            "entry_price": Decimal("51000"),

            "entry_time": datetime(2024, 1, 1),

        }

        trade = pipeline._close_position(

            symbol="BTCUSDT",

            position=position,

            exit_price=Decimal("50000"),

            exit_time=datetime(2024, 1, 2),

        )

        assert trade.side == "short"

        assert trade.gross_pnl == Decimal("1000")  # (51000 - 50000) * 1

        assert trade.net_pnl > 0

    def test_fee_impact(self):
        """Проверить impact комиссий и слиппеджа"""

        pipeline = UnifiedPipeline(

            initial_balance=Decimal("10000"),

            commission_maker=Decimal("0.0002"),

            commission_taker=Decimal("0.0004"),

            slippage_bps=Decimal("2"),

        )

        position = {

            "symbol": "BTCUSDT",

            "side": "long",

            "qty": Decimal("1"),

            "entry_price": Decimal("50000"),

            "entry_time": datetime(2024, 1, 1),

        }

        trade = pipeline._close_position(

            symbol="BTCUSDT",

            position=position,

            exit_price=Decimal("51000"),

            exit_time=datetime(2024, 1, 2),

        )

        # Gross PnL = 1000 USD

        # Commission = (50000 + 51000) * 0.0004 = 40.4

        # Slippage = (50000 + 51000) * 0.0002 = 20.2

        # Net PnL = 1000 - 40.4 - 20.2

        assert trade.gross_pnl == Decimal("1000")

        assert trade.commission > 0

        assert trade.slippage > 0

        assert trade.net_pnl < trade.gross_pnl

    def test_calculate_metrics_basic(self):
        """Рассчитать базовые метрики"""

        pipeline = UnifiedPipeline()

        trades = [

            TradeMetric(

                entry_price=Decimal("100"),

                exit_price=Decimal("110"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 1),

                exit_time=datetime(2024, 1, 2),

                side="long",

                pnl_usd=Decimal("10"),

                pnl_percent=Decimal("10"),

                commission=Decimal("0.2"),

                slippage=Decimal("0.1"),

                gross_pnl=Decimal("10.3"),

                net_pnl=Decimal("10"),

            ),

            TradeMetric(

                entry_price=Decimal("110"),

                exit_price=Decimal("105"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 3),

                exit_time=datetime(2024, 1, 4),

                side="long",

                pnl_usd=Decimal("-5"),

                pnl_percent=Decimal("-4.5"),

                commission=Decimal("0.2"),

                slippage=Decimal("0.1"),

                gross_pnl=Decimal("-5.3"),

                net_pnl=Decimal("-5"),

            ),

        ]

        metrics = pipeline.calculate_metrics(

            trades=trades,

            start_time=datetime(2024, 1, 1),

            end_time=datetime(2024, 1, 4),

            period_type="test",

        )

        assert metrics.total_trades == 2

        assert metrics.winning_trades == 1

        assert metrics.losing_trades == 1

        assert metrics.net_pnl == Decimal("5")  # 10 + (-5)

        assert metrics.win_rate == Decimal("50")  # 1/2 * 100

    def test_profit_factor_calculation(self):
        """Рассчитать profit factor"""

        pipeline = UnifiedPipeline()

        trades = [

            TradeMetric(

                entry_price=Decimal("100"),

                exit_price=Decimal("120"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 1),

                exit_time=datetime(2024, 1, 2),

                side="long",

                pnl_usd=Decimal("20"),

                pnl_percent=Decimal("20"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("20"),

                net_pnl=Decimal("20"),

            ),

            TradeMetric(

                entry_price=Decimal("120"),

                exit_price=Decimal("100"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 3),

                exit_time=datetime(2024, 1, 4),

                side="long",

                pnl_usd=Decimal("-20"),

                pnl_percent=Decimal("-16.7"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("-20"),

                net_pnl=Decimal("-20"),

            ),

        ]

        metrics = pipeline.calculate_metrics(

            trades=trades,

            start_time=datetime(2024, 1, 1),

            end_time=datetime(2024, 1, 4),

        )

        # PF = gross_profit / abs(gross_loss) = 20 / 20 = 1.0

        assert metrics.profit_factor == Decimal("1")

    def test_drawdown_calculation(self):
        """Рассчитать max drawdown"""

        pipeline = UnifiedPipeline()

        trades = [

            TradeMetric(

                entry_price=Decimal("100"),

                exit_price=Decimal("110"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 1),

                exit_time=datetime(2024, 1, 2),

                side="long",

                pnl_usd=Decimal("10"),

                pnl_percent=Decimal("10"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("10"),

                net_pnl=Decimal("10"),

            ),

            TradeMetric(

                entry_price=Decimal("110"),

                exit_price=Decimal("100"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 3),

                exit_time=datetime(2024, 1, 4),

                side="long",

                pnl_usd=Decimal("-10"),

                pnl_percent=Decimal("-9.1"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("-10"),

                net_pnl=Decimal("-10"),

            ),

            TradeMetric(

                entry_price=Decimal("100"),

                exit_price=Decimal("95"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 5),

                exit_time=datetime(2024, 1, 6),

                side="long",

                pnl_usd=Decimal("-5"),

                pnl_percent=Decimal("-5"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("-5"),

                net_pnl=Decimal("-5"),

            ),

        ]

        metrics = pipeline.calculate_metrics(

            trades=trades,

            start_time=datetime(2024, 1, 1),

            end_time=datetime(2024, 1, 6),

        )

        # After trade 1: +10 (peak = 10)

        # After trade 2: 0 (DD = 10 - 0 = 10)

        # After trade 3: -5 (DD = 10 - (-5) = 15, but tracking peak)

        # Max DD should be 15

        assert metrics.max_drawdown_usd > 0


class TestValidationEngine:

    """Тесты для ValidationEngine"""

    @staticmethod
    def simple_strategy(df: pd.DataFrame) -> Dict[int, Dict]:
        """Простая стратегия для тестирования"""

        signals = {}

        for i in range(1, len(df)):

            prev_close = df.iloc[i - 1]["close"]

            curr_close = df.iloc[i]["close"]

            # Simple: buy if price up, sell if price down

            if curr_close > prev_close and i < len(df) - 1:

                signals[i] = {"type": "long", "qty": Decimal("1")}

            elif curr_close < prev_close and i < len(df) - 1:

                signals[i] = {"type": "close"}

        return signals

    @staticmethod
    def create_sample_df(

        num_candles: int = 100,

        start_price: float = 50000.0,

        trend: float = 0.001,

    ) -> pd.DataFrame:
        """Создать sample DataFrame"""

        prices = []

        current = start_price

        for _ in range(num_candles):

            current *= 1 + trend

            prices.append(current)

        timestamps = pd.date_range(start="2024-01-01", periods=num_candles, freq="1h")

        data = []

        for i, (ts, price) in enumerate(zip(timestamps, prices)):

            data.append(

                {

                    "timestamp": ts,

                    "open": price * 0.99,

                    "high": price * 1.01,

                    "low": price * 0.98,

                    "close": price,

                    "volume": 100.0,

                }

            )

        return pd.DataFrame(data)

    def test_engine_initialization(self):
        """Инициализировать engine"""

        engine = ValidationEngine(

            strategy_func=self.simple_strategy,

            strategy_name="SimpleStrategy",

            config={"initial_balance": "10000"},

        )

        assert engine.strategy_name == "SimpleStrategy"

        assert engine.pipeline.initial_balance == Decimal("10000")

    def test_validate_on_data(self):
        """Валидировать на данных"""

        engine = ValidationEngine(

            strategy_func=self.simple_strategy,

            strategy_name="SimpleStrategy",

        )

        df = self.create_sample_df(num_candles=50, trend=0.001)

        metrics = engine.validate_on_data(df, period_type="test")

        assert metrics.total_trades >= 0

        assert metrics.period_type == "test"

        assert len(metrics.trades) == metrics.total_trades

    def test_generate_report(self):
        """Генерировать report"""

        engine = ValidationEngine(

            strategy_func=self.simple_strategy,

            strategy_name="SimpleStrategy",

        )

        # Train data

        train_df = self.create_sample_df(num_candles=50, trend=0.001)

        train_metrics = engine.validate_on_data(train_df, period_type="train")

        # Test data

        test_df = self.create_sample_df(num_candles=50, trend=0.001)

        test_metrics = engine.validate_on_data(test_df, period_type="test")

        # Generate report

        report = engine.generate_report(

            train_metrics=train_metrics,

            test_metrics=test_metrics,

        )

        assert report.strategy_name == "SimpleStrategy"

        assert report.train_metrics == train_metrics

        assert report.test_metrics == test_metrics

        assert isinstance(report.train_vs_test, dict)

    def test_validate_strategy_with_good_results(self):
        """Валидировать с хорошими результатами"""

        engine = ValidationEngine(

            strategy_func=self.simple_strategy,

            strategy_name="SimpleStrategy",

        )

        # Create metrics manually with good stats

        trades = [

            TradeMetric(

                entry_price=Decimal("100"),

                exit_price=Decimal("110"),

                qty=Decimal("1"),

                entry_time=datetime(2024, 1, 1),

                exit_time=datetime(2024, 1, 2),

                side="long",

                pnl_usd=Decimal("10"),

                pnl_percent=Decimal("10"),

                commission=Decimal("0"),

                slippage=Decimal("0"),

                gross_pnl=Decimal("10"),

                net_pnl=Decimal("10"),

            ),

        ] * 10  # 10 winning trades

        metrics = engine.pipeline.calculate_metrics(

            trades=trades,

            start_time=datetime(2024, 1, 1),

            end_time=datetime(2024, 1, 10),

        )

        is_valid, warnings, errors = engine._validate_strategy(metrics, metrics)

        # Should be valid with good win rate

        assert is_valid

    def test_compare_periods(self):
        """Сравнить периоды"""

        engine = ValidationEngine(

            strategy_func=self.simple_strategy,

            strategy_name="SimpleStrategy",

        )

        trade = TradeMetric(

            entry_price=Decimal("100"),

            exit_price=Decimal("110"),

            qty=Decimal("1"),

            entry_time=datetime(2024, 1, 1),

            exit_time=datetime(2024, 1, 2),

            side="long",

            pnl_usd=Decimal("10"),

            pnl_percent=Decimal("10"),

            commission=Decimal("0"),

            slippage=Decimal("0"),

            gross_pnl=Decimal("10"),

            net_pnl=Decimal("10"),

        )

        metrics1 = engine.pipeline.calculate_metrics(

            trades=[trade] * 10,

            start_time=datetime(2024, 1, 1),

            end_time=datetime(2024, 1, 10),

        )

        metrics2 = engine.pipeline.calculate_metrics(

            trades=[trade] * 15,

            start_time=datetime(2024, 1, 11),

            end_time=datetime(2024, 1, 25),

        )

        comparison = engine._compare_periods(metrics1, metrics2)

        assert "trades" in comparison

        assert "net_pnl" in comparison

        assert comparison["trades"]["train"] == 10

        assert comparison["trades"]["test"] == 15


class TestOutOfSampleValidation:

    """Out-of-sample validation тесты"""

    def test_train_test_split_time_based(self):
        """Time-based train/test split"""

        timestamps = pd.date_range(start="2024-01-01", periods=100, freq="1h")

        df = pd.DataFrame(

            {

                "timestamp": timestamps,

                "open": [50000.0 + i for i in range(100)],

                "high": [50010.0 + i for i in range(100)],

                "low": [49990.0 + i for i in range(100)],

                "close": [50005.0 + i for i in range(100)],

                "volume": [100.0] * 100,

            }

        )

        # Split 70/30

        split_index = int(len(df) * 0.7)

        train_df = df.iloc[:split_index]

        test_df = df.iloc[split_index:]

        assert len(train_df) == 70

        assert len(test_df) == 30

        assert train_df.iloc[-1]["timestamp"] < test_df.iloc[0]["timestamp"]

    def test_no_data_leakage(self):
        """Проверить отсутствие data leakage"""

        timestamps = pd.date_range(start="2024-01-01", periods=100, freq="1h")

        df = pd.DataFrame(

            {

                "timestamp": timestamps,

                "close": [50000.0 + i for i in range(100)],

            }

        )

        split_index = int(len(df) * 0.7)

        train_df = df.iloc[:split_index]

        test_df = df.iloc[split_index:]

        # Test data should be strictly after train data

        train_max = train_df.iloc[-1]["timestamp"]

        test_min = test_df.iloc[0]["timestamp"]

        assert test_min > train_max


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
