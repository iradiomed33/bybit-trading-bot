# -*- coding: utf-8 -*-

"""

Backtest Runner - E2 EPIC


Минимальный бэктестер для прогона стратегий на исторических данных.


Особенности:

- Загрузка OHLCV данных из БД/CSV

- Воспроизведение свечей в хронологическом порядке

- Integration с PaperTradingSimulator для реалистичных fills

- Time-based train/test split для out-of-sample тестирования

- Детальные отчеты по метрикам


Workflow:

1. Загрузить исторические данные

2. Разделить на train/test по времени

3. Для каждого разделения:

   - Инициализировать новый симулятор

   - Прогнать all candles через стратегии

   - Собрать metrics

4. Сравнить результаты train vs test

"""


from datetime import datetime

from decimal import Decimal

from typing import Dict, Tuple, Optional, Any, Callable

import logging

from dataclasses import dataclass

import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:

    """Конфигурация для бэктеста"""

    initial_balance: Decimal = Decimal("10000")

    commission_maker: Decimal = Decimal("0.0002")

    commission_taker: Decimal = Decimal("0.0004")

    # Slippage configuration

    slippage_bps: Decimal = Decimal("2")  # Base slippage in basis points (2 bps = 0.0002)

    slippage_volatility_factor_enabled: bool = True

    slippage_volume_factor_enabled: bool = True

    # Train/test split

    test_size_percent: float = 30.0  # 30% для тестирования

    # Другие параметры

    symbol: str = "BTCUSDT"

    timeframe: str = "1h"  # 1h, 4h, 1d и т.д.


class HistoricalDataLoader:

    """Загрузчик исторических данных"""

    def __init__(self, symbol: str = "BTCUSDT", timeframe: str = "1h"):
        """

        Инициализировать загрузчик.


        Args:

            symbol: Торговая пара

            timeframe: Таймфрейм (1h, 4h, 1d)

        """

        self.symbol = symbol

        self.timeframe = timeframe

    @staticmethod
    def load_from_csv(filepath: str) -> "Any":
        """

        Загрузить данные из CSV файла.


        Args:

            filepath: Путь к CSV файлу


        Returns:

            DataFrame с columns: timestamp, open, high, low, close, volume

        """

        import pandas as pd

        df = pd.read_csv(filepath)

        # Убедиться что есть необходимые columns

        required_cols = {"open", "high", "low", "close", "volume"}

        if not required_cols.issubset(set(df.columns)):

            raise ValueError(f"CSV must contain columns: {required_cols}")

        # Конвертировать timestamp если есть

        if "timestamp" in df.columns:

            df["timestamp"] = pd.to_datetime(df["timestamp"])

        elif "time" in df.columns:

            df["timestamp"] = pd.to_datetime(df["time"])

            df = df.drop("time", axis=1)

        else:

            # Создать timestamp from index если его нет

            df["timestamp"] = pd.date_range(start="2020-01-01", periods=len(df), freq="1h")

        # Сортировать по времени

        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Loaded {len(df)} candles from {filepath}")

        return df

    @staticmethod
    def load_from_db(db, symbol: str, start_date: datetime, end_date: datetime) -> "Any":
        """

        Загрузить данные из базы.


        Args:

            db: Database объект

            symbol: Торговая пара

            start_date: Начальная дата

            end_date: Конечная дата


        Returns:

            DataFrame с OHLCV данными

        """

        import pandas as pd

        # TODO: Реализовать когда будет доступ к схеме БД

        logger.warning("load_from_db not yet implemented")

        return pd.DataFrame()

    @staticmethod
    def generate_sample_data(

        num_candles: int = 1000,

        start_price: Decimal = Decimal("40000"),

        volatility: Decimal = Decimal("0.02"),

    ) -> "Any":
        """

        Генерировать sample исторические данные для тестирования.


        Args:

            num_candles: Количество свечей

            start_price: Начальная цена

            volatility: Волатильность (0.02 = 2%)


        Returns:

            DataFrame с OHLCV данными

        """

        import pandas as pd

        import random

        import math

        random.seed(42)  # Reproducibility

        timestamps = pd.date_range(start="2023-01-01", periods=num_candles, freq="1h")

        # Generate price series using random walk with drift

        current_price = float(start_price)

        prices = [current_price]

        for _ in range(num_candles - 1):

            # Random normal-like distribution using polar method

            u1 = random.random()

            u2 = random.random()

            z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

            return_val = float(volatility) * z

            current_price = current_price * (1 + return_val)

            prices.append(current_price)

        data = []

        for i, timestamp in enumerate(timestamps):

            base_price = Decimal(str(prices[i]))

            # Generate OHLC

            u1 = random.random()

            u2 = random.random()

            close_return = (

                float(volatility)

                * math.sqrt(-2 * math.log(u1 or 0.001))

                * math.cos(2 * math.pi * u2)

            )

            close_price = base_price * Decimal(str(1 + close_return * 0.1))

            open_price = base_price

            high_price = max(open_price, close_price) * Decimal(

                str(1 + abs(float(volatility) * 0.25))

            )

            low_price = min(open_price, close_price) * Decimal(

                str(1 - abs(float(volatility) * 0.25))

            )

            volume = Decimal(str(random.uniform(100, 1000)))

            data.append(

                {

                    "timestamp": timestamp,

                    "open": float(open_price),

                    "high": float(high_price),

                    "low": float(low_price),

                    "close": float(close_price),

                    "volume": float(volume),

                }

            )

        df = pd.DataFrame(data)

        final_price = prices[-1]

        logger.info(

            f"Generated {num_candles} sample candles: ${float(start_price):.2f} -> ${final_price:.2f}"

        )

        return df


class TrainTestSplitter:

    """

    Time-based train/test splitter.


    Важно: НЕ используем random shuffle! Раздеяем по времени,

    чтобы избежать data leakage.

    """

    @staticmethod
    def split(

        df: "Any",

        test_size_percent: float = 30.0,

    ) -> Tuple["Any", "Any"]:
        """

        Разделить данные на train и test по времени.


        Args:

            df: DataFrame с OHLCV данными (должен быть отсортирован по времени)

            test_size_percent: % данных для теста (по умолчанию 30%)


        Returns:

            (train_df, test_df)

        """

        if not 0 < test_size_percent < 100:

            raise ValueError("test_size_percent must be between 0 and 100")

        # Убедиться что отсортирован по времени

        df = df.sort_values("timestamp").reset_index(drop=True)

        # Вычислить split point

        split_index = int(len(df) * (1 - test_size_percent / 100))

        train_df = df.iloc[:split_index].copy()

        test_df = df.iloc[split_index:].copy()

        logger.info(

            f"Train/test split: {len(train_df)} train candles "

            f"({train_df['timestamp'].min()} to {train_df['timestamp'].max()}), "

            f"{len(test_df)} test candles "

            f"({test_df['timestamp'].min()} to {test_df['timestamp'].max()})"

        )

        return train_df, test_df

    @staticmethod
    def validate_no_leakage(train_df: "Any", test_df: "Any") -> bool:
        """

        Убедиться что нет data leakage (test данные не смешаны с train).


        Args:

            train_df: Train данные

            test_df: Test данные


        Returns:

            True если нет leakage

        """

        if len(train_df) == 0 or len(test_df) == 0:

            return False

        train_max_time = train_df["timestamp"].max()

        test_min_time = test_df["timestamp"].min()

        # Test данные должны быть ПОСЛЕ train данных

        if test_min_time <= train_max_time:

            logger.error(

                f"Data leakage detected! Test min time {test_min_time} <= Train max time {train_max_time}"

            )

            return False

        return True


class BacktestRunner:

    """

    Минимальный backtest runner.


    Прогоняет стратегии на исторических данных используя

    PaperTradingSimulator для реалистичных fills и комиссий.

    """

    def __init__(self, config: BacktestConfig = None):
        """

        Инициализировать runner.


        Args:

            config: BacktestConfig

        """

        self.config = config or BacktestConfig()

        self.results = {}  # Dict для хранения результатов

    def run_backtest(

        self,

        df: "Any",

        strategy_func,  # Callable: df -> signal or None

        symbol: str = "BTCUSDT",

        name: str = "backtest",

    ) -> Dict[str, Any]:
        """

        Прогнать бэктест на исторических данных.


        Args:

            df: DataFrame с OHLCV данными

            strategy_func: Функция которая принимает df и возвращает сигнал или None

            symbol: Торговая пара

            name: Имя для результатов


        Returns:

            Dict с результатами: trades, metrics, equity_curve

        """

        from execution.paper_trading_simulator import (

            PaperTradingSimulator,

            PaperTradingConfig,

        )

        from execution.trade_metrics import TradeMetricsCalculator, EquityCurve

        # Инициализировать симулятор

        paper_config = PaperTradingConfig(

            initial_balance=self.config.initial_balance,

            maker_commission=self.config.commission_maker,

            taker_commission=self.config.commission_taker,

            slippage_bps=self.config.slippage_bps,

            slippage_volatility_factor_enabled=self.config.slippage_volatility_factor_enabled,

            slippage_volume_factor_enabled=self.config.slippage_volume_factor_enabled,

        )

        simulator = PaperTradingSimulator(paper_config)

        equity_curve = EquityCurve()

        logger.info(f"Running backtest '{name}' on {len(df)} candles...")

        trades_count = 0

        # Прогнать через каждую свечу

        for idx, row in df.iterrows():

            # Преобразовать row в DataFrame для strategy_func

            df_up_to_now = df.iloc[: idx + 1].copy()

            # Получить сигнал от стратегии

            try:

                signal = strategy_func(df_up_to_now)

            except Exception as e:

                logger.debug(f"Strategy error at candle {idx}: {e}")

                continue

            if signal:

                # Отправить ордер

                current_price = Decimal(str(row["close"]))

                try:

                    side = "Buy" if signal.get("signal") == "long" else "Sell"

                    # Вычислить количество (1% от balance)

                    account_summary = simulator.get_account_summary()

                    balance = Decimal(str(account_summary["equity"]))

                    qty = balance * Decimal("0.01") / current_price

                    # Отправить market ордер

                    order_id, success, msg = simulator.submit_market_order(

                        symbol=symbol,

                        side=side,

                        qty=qty,

                        current_price=current_price,

                    )

                    if success:

                        trades_count += 1

                        logger.debug(

                            f"Candle {idx}: {side} signal filled at ${float(current_price):.2f}"

                        )

                except Exception as e:

                    logger.debug(f"Order submission error: {e}")

                    continue

            # Обновить цены и equity curve

            simulator.update_market_prices({symbol: Decimal(str(row["close"]))})

            equity = simulator.get_equity()

            equity_curve.add_point(idx, equity)

            # Проверить SL/TP

            triggered = simulator.check_sl_tp(Decimal(str(row["close"])))

            for sym, trigger_type in triggered.items():

                simulator.close_position_on_trigger(

                    symbol=sym,

                    trigger_type=trigger_type,

                    exit_price=Decimal(str(row["close"])),

                )

        # Вычислить метрики

        trades = simulator.get_trades()

        metrics = TradeMetricsCalculator.calculate(

            trades,

            self.config.initial_balance,

            equity_curve,

        )

        result = {

            "name": name,

            "symbol": symbol,

            "trades": trades,

            "trades_count": len(trades),

            "metrics": metrics,

            "equity_curve": equity_curve,

            "simulator": simulator,

            "start_price": Decimal(str(df.iloc[0]["close"])),

            "end_price": Decimal(str(df.iloc[-1]["close"])),

            "start_date": df.iloc[0]["timestamp"],

            "end_date": df.iloc[-1]["timestamp"],

            "candles_count": len(df),

        }

        logger.info(

            f"Backtest '{name}' complete: {len(trades)} trades, "

            f"${float(simulator.get_equity()):.2f} equity, "

            f"PF={float(metrics.profit_factor):.2f}"

        )

        return result

    def run_train_test(

        self,

        df: "Any",

        strategy_func,

        symbol: str = "BTCUSDT",

        name: str = "strategy",

    ) -> Dict[str, Dict[str, Any]]:
        """

        Прогнать бэктест на train и test данных раздельно.


        Args:

            df: Полный DataFrame с OHLCV данными

            strategy_func: Функция стратегии

            symbol: Торговая пара

            name: Имя стратегии


        Returns:

            Dict с keys 'train' и 'test', каждый содержит результаты

        """

        # Разделить данные

        train_df, test_df = TrainTestSplitter.split(df, self.config.test_size_percent)

        # Проверить что нет leakage

        if not TrainTestSplitter.validate_no_leakage(train_df, test_df):

            raise ValueError("Data leakage detected in train/test split")

        # Прогнать на train данных

        train_result = self.run_backtest(train_df, strategy_func, symbol, f"{name}_train")

        # Прогнать на test данных

        test_result = self.run_backtest(test_df, strategy_func, symbol, f"{name}_test")

        return {

            "train": train_result,

            "test": test_result,

            "name": name,

            "train_size": len(train_df),

            "test_size": len(test_df),

        }

    def run_unified_validation(

        self,

        df: pd.DataFrame,

        strategy_func: Callable,

        strategy_name: str = "Strategy",

        config: Optional[Dict] = None,

    ) -> "Any":
        """

        Прогнать unified VAL-001 validation pipeline.


        Ensures identical logic across backtest/forward/live.


        Args:

            df: OHLCV DataFrame

            strategy_func: Strategy function (df -> signals dict)

            strategy_name: Strategy name

            config: Optional config dict


        Returns:

            ValidationReport with train/test metrics

        """

        from validation.validation_engine import ValidationEngine

        # Инициализировать engine

        engine = ValidationEngine(

            strategy_func=strategy_func,

            strategy_name=strategy_name,

            config=config or {},

        )

        # Разделить данные

        train_df, test_df = TrainTestSplitter.split(df, self.config.test_size_percent)

        # Валидировать на train данных

        logger.info(f"Running validation on {len(train_df)} train candles...")

        train_metrics = engine.validate_on_data(train_df, period_type="train")

        # Валидировать на test данных

        logger.info(f"Running validation on {len(test_df)} test candles...")

        test_metrics = engine.validate_on_data(test_df, period_type="test")

        # Генерировать report

        report = engine.generate_report(

            train_metrics=train_metrics,

            test_metrics=test_metrics,

        )

        logger.info(

            f"Validation complete: Train PF={float(train_metrics.profit_factor):.2f}, "

            f"Test PF={float(test_metrics.profit_factor):.2f}"

        )

        return report
