"""

VAL-001: Unified Validation Pipeline


Один и тот же пайплайн для backtest, forward test и live:

    candles → features → signal → execution model → metrics


Валидирует что стратегия работает одинаково во всех условиях.

"""


from dataclasses import dataclass, field

from decimal import Decimal

from datetime import datetime, timedelta

from typing import Dict, List, Optional, Any, Callable, Tuple

from enum import Enum

import logging

import json


logger = logging.getLogger(__name__)


class PeriodType(Enum):

    """Тип периода данных"""

    TRAIN = "train"  # Обучающий (для туна параметров)

    TEST = "test"  # Out-of-sample тест

    FORWARD = "forward"  # Forward test на новых данных

    LIVE = "live"  # Live trading


@dataclass
class TradeMetric:

    """Метрика одной сделки"""

    entry_price: Decimal

    exit_price: Decimal

    qty: Decimal

    entry_time: datetime

    exit_time: datetime

    side: str  # long/short

    pnl_usd: Decimal  # PnL в USD

    pnl_percent: Decimal  # PnL в %

    commission: Decimal  # Комиссия за открытие + закрытие

    slippage: Decimal  # Слиппедж

    gross_pnl: Decimal  # PnL до комиссий/слиппеджа

    net_pnl: Decimal  # PnL после комиссий/слиппеджа


@dataclass
class ValidationMetrics:

    """Метрики валидации стратегии"""

    # Основные метрики

    total_trades: int = 0

    winning_trades: int = 0

    losing_trades: int = 0

    # PnL метрики

    gross_pnl: Decimal = Decimal("0")  # До комиссий

    net_pnl: Decimal = Decimal("0")  # После комиссий

    total_commission: Decimal = Decimal("0")

    total_slippage: Decimal = Decimal("0")

    # Drawdown метрики

    max_drawdown_usd: Decimal = Decimal("0")

    max_drawdown_percent: Decimal = Decimal("0")

    current_drawdown_usd: Decimal = Decimal("0")

    current_drawdown_percent: Decimal = Decimal("0")

    # Ratio метрики

    profit_factor: Decimal = Decimal("0")  # Gross profit / Gross loss

    win_rate: Decimal = Decimal("0")  # Winning trades / Total trades

    expectancy: Decimal = Decimal("0")  # Avg PnL per trade

    # Exposure метрики

    max_exposure_usd: Decimal = Decimal("0")

    avg_exposure_usd: Decimal = Decimal("0")

    max_open_positions: int = 0

    # Time метрики

    avg_trade_duration: timedelta = field(default_factory=lambda: timedelta(0))

    total_time_in_market: timedelta = field(default_factory=lambda: timedelta(0))

    # Period info

    period_type: str = "unknown"

    start_date: datetime = field(default_factory=datetime.now)

    end_date: datetime = field(default_factory=datetime.now)

    candles_processed: int = 0

    # Trades list

    trades: List[TradeMetric] = field(default_factory=list)


@dataclass
class ValidationReport:

    """Полный отчёт по валидации"""

    strategy_name: str

    timestamp: datetime = field(default_factory=datetime.now)

    # Результаты по периодам

    train_metrics: Optional[ValidationMetrics] = None

    test_metrics: Optional[ValidationMetrics] = None

    forward_metrics: Optional[ValidationMetrics] = None

    live_metrics: Optional[ValidationMetrics] = None

    # Сравнение train vs test

    train_vs_test: Dict[str, Any] = field(default_factory=dict)

    # Conclusions

    is_valid: bool = False

    warnings: List[str] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)

    # Raw data for plotting

    equity_curves: Dict[str, List[Decimal]] = field(default_factory=dict)

    drawdown_curves: Dict[str, List[Decimal]] = field(default_factory=dict)


class UnifiedPipeline:

    """

    Unified validation pipeline для всех типов тестирования.


    Гарантирует что:

    1. Логика одинакова для backtest, forward, и live

    2. Все метрики считаются одинаково

    3. Fee impact и slippage консистентны

    """

    def __init__(

        self,

        initial_balance: Decimal = Decimal("10000"),

        commission_maker: Decimal = Decimal("0.0002"),

        commission_taker: Decimal = Decimal("0.0004"),

        slippage_bps: Decimal = Decimal("2"),

    ):
        """

        Инициализировать pipeline.


        Args:

            initial_balance: Начальный баланс

            commission_maker: Maker комиссия (0.0002 = 0.02%)

            commission_taker: Taker комиссия (0.0004 = 0.04%)

            slippage_bps: Слиппедж в basis points (2 = 0.02%)

        """

        self.initial_balance = initial_balance

        self.commission_maker = commission_maker

        self.commission_taker = commission_taker

        self.slippage_bps = slippage_bps

        self.equity = initial_balance

        self.trades: List[TradeMetric] = []

        self.equity_history: List[Decimal] = [initial_balance]

        self.drawdown_history: List[Decimal] = [Decimal("0")]

        self.peak_equity = initial_balance

    def process_candle(

        self,

        candle: Dict,

        signal: Optional[Dict],

        current_positions: Dict = None,

    ) -> Dict:
        """

        Обработать одну свечу (канонический пайплайн).


        Args:

            candle: {'timestamp': dt, 'open': p, 'high': p, 'low': p, 'close': p, 'volume': v}

            signal: {'type': 'long'|'short'|'close', 'qty': Decimal, 'comment': str} или None

            current_positions: Текущие открытые позиции


        Returns:

            Dict с результатами: trades_closed, position_opened, metrics

        """

        result = {

            "trades_closed": [],

            "position_opened": None,

            "metrics": {},

        }

        if not signal:

            return result

        # Обработать signal

        if signal.get("type") == "close" and current_positions:

            # Закрыть позицию

            for symbol, pos in current_positions.items():

                trade = self._close_position(

                    symbol=symbol,

                    position=pos,

                    exit_price=Decimal(str(candle["close"])),

                    exit_time=candle["timestamp"],

                )

                if trade:

                    self.trades.append(trade)

                    result["trades_closed"].append(trade)

        elif signal.get("type") in ("long", "short"):

            # Открыть позицию

            result["position_opened"] = {

                "symbol": signal.get("symbol", "BTCUSDT"),

                "side": signal["type"],

                "qty": signal.get("qty", Decimal("1")),

                "entry_price": Decimal(str(candle["close"])),

                "entry_time": candle["timestamp"],

            }

        # Обновить equity после сделок

        self._update_equity_after_trades(result["trades_closed"])

        return result

    def _close_position(

        self,

        symbol: str,

        position: Dict,

        exit_price: Decimal,

        exit_time: datetime,

    ) -> Optional[TradeMetric]:
        """Закрыть позицию и вернуть TradeMetric"""

        if not isinstance(exit_price, Decimal):

            exit_price = Decimal(str(exit_price))

        entry_price = position["entry_price"]

        qty = position["qty"]

        side = position["side"]

        # Рассчитать PnL

        if side == "long":

            gross_pnl = (exit_price - entry_price) * qty

        else:  # short

            gross_pnl = (entry_price - exit_price) * qty

        # Рассчитать комиссии (открытие + закрытие)

        entry_notional = entry_price * qty

        exit_notional = exit_price * qty

        commission = (entry_notional + exit_notional) * self.commission_taker

        # Рассчитать слиппедж

        slippage = entry_notional * (self.slippage_bps / Decimal("10000"))

        slippage += exit_notional * (self.slippage_bps / Decimal("10000"))

        # Net PnL

        net_pnl = gross_pnl - commission - slippage

        gross_pnl_percent = (exit_price - entry_price) / entry_price * Decimal("100")

        if side == "short":

            gross_pnl_percent = (entry_price - exit_price) / entry_price * Decimal("100")

        trade = TradeMetric(

            entry_price=entry_price,

            exit_price=exit_price,

            qty=qty,

            entry_time=position["entry_time"],

            exit_time=exit_time,

            side=side,

            pnl_usd=net_pnl,

            pnl_percent=gross_pnl_percent,

            commission=commission,

            slippage=slippage,

            gross_pnl=gross_pnl,

            net_pnl=net_pnl,

        )

        return trade

    def _update_equity_after_trades(self, trades_closed: List[TradeMetric]) -> None:
        """Обновить equity после закрытия сделок"""

        for trade in trades_closed:

            self.equity += trade.net_pnl

        # Обновить историю

        self.equity_history.append(self.equity)

        # Обновить drawdown

        if self.equity > self.peak_equity:

            self.peak_equity = self.equity

        drawdown = self.peak_equity - self.equity

        self.drawdown_history.append(drawdown)

    def calculate_metrics(

        self,

        trades: List[TradeMetric],

        start_time: datetime,

        end_time: datetime,

        period_type: str = "unknown",

    ) -> ValidationMetrics:
        """

        Рассчитать метрики для периода.


        Args:

            trades: Список сделок

            start_time: Начало периода

            end_time: Конец периода

            period_type: Тип периода (train/test/forward/live)


        Returns:

            ValidationMetrics

        """

        metrics = ValidationMetrics(

            trades=trades,

            period_type=period_type,

            start_date=start_time,

            end_date=end_time,

            total_trades=len(trades),

        )

        if len(trades) == 0:

            return metrics

        # PnL метрики

        gross_profits = sum(t.gross_pnl for t in trades if t.gross_pnl > 0)

        gross_losses = sum(t.gross_pnl for t in trades if t.gross_pnl < 0)

        metrics.gross_pnl = sum(t.gross_pnl for t in trades)

        metrics.net_pnl = sum(t.net_pnl for t in trades)

        metrics.total_commission = sum(t.commission for t in trades)

        metrics.total_slippage = sum(t.slippage for t in trades)

        # Win rate

        metrics.winning_trades = sum(1 for t in trades if t.net_pnl > 0)

        metrics.losing_trades = sum(1 for t in trades if t.net_pnl < 0)

        metrics.win_rate = Decimal(metrics.winning_trades) / len(trades) * Decimal("100")

        # Profit factor

        if abs(gross_losses) > 0:

            metrics.profit_factor = gross_profits / abs(gross_losses)

        else:

            metrics.profit_factor = Decimal("inf") if gross_profits > 0 else Decimal("0")

        # Expectancy (avg PnL per trade)

        metrics.expectancy = metrics.net_pnl / len(trades)

        # Drawdown

        cumulative_pnl = Decimal("0")

        peak_cumulative = Decimal("0")

        max_dd = Decimal("0")

        for trade in trades:

            cumulative_pnl += trade.net_pnl

            if cumulative_pnl > peak_cumulative:

                peak_cumulative = cumulative_pnl

            current_dd = peak_cumulative - cumulative_pnl

            if current_dd > max_dd:

                max_dd = current_dd

        metrics.max_drawdown_usd = max_dd

        metrics.max_drawdown_percent = max_dd / self.initial_balance * Decimal("100")

        # Trade duration

        if len(trades) > 0:

            total_duration = sum((t.exit_time - t.entry_time).total_seconds() for t in trades)

            metrics.avg_trade_duration = timedelta(seconds=total_duration / len(trades))

            first_entry = min(t.entry_time for t in trades)

            last_exit = max(t.exit_time for t in trades)

            metrics.total_time_in_market = last_exit - first_entry

        return metrics


class ValidationEngine:

    """

    Валидационный движок для проверки стратегий.


    Запускает стратегию через единый pipeline на разных периодах

    и генерирует report.

    """

    def __init__(

        self,

        strategy_func: Callable,

        strategy_name: str,

        config: Dict = None,

    ):
        """

        Инициализировать engine.


        Args:

            strategy_func: Callable(df) -> List[Dict] (сигналы)

            strategy_name: Имя стратегии

            config: Конфигурация (initial_balance, commission, slippage, etc.)

        """

        self.strategy_func = strategy_func

        self.strategy_name = strategy_name

        self.config = config or {}

        # Инициализировать pipeline

        self.pipeline = UnifiedPipeline(

            initial_balance=Decimal(str(self.config.get("initial_balance", "10000"))),

            commission_maker=Decimal(str(self.config.get("commission_maker", "0.0002"))),

            commission_taker=Decimal(str(self.config.get("commission_taker", "0.0004"))),

            slippage_bps=Decimal(str(self.config.get("slippage_bps", "2"))),

        )

    def validate_on_data(

        self,

        df: "Any",

        period_type: str = "unknown",

    ) -> ValidationMetrics:
        """

        Валидировать стратегию на данных.


        Args:

            df: DataFrame с OHLCV данными (timestamp, open, high, low, close, volume)

            period_type: Тип периода (train/test/forward/live)


        Returns:

            ValidationMetrics

        """

        logger.info(f"Validating {self.strategy_name} on {len(df)} candles ({period_type})")

        # Получить сигналы от стратегии

        signals = self.strategy_func(df)  # List[Dict] или Dict

        signal_dict = self._normalize_signals(signals)

        trades = []

        current_positions = {}

        # Прогнать свечи через pipeline

        for idx, row in df.iterrows():

            candle = {

                "timestamp": row["timestamp"],

                "open": Decimal(str(row["open"])),

                "high": Decimal(str(row["high"])),

                "low": Decimal(str(row["low"])),

                "close": Decimal(str(row["close"])),

                "volume": Decimal(str(row["volume"])),

            }

            signal = signal_dict.get(idx)

            result = self.pipeline.process_candle(candle, signal, current_positions)

            trades.extend(result["trades_closed"])

            if result["position_opened"]:

                current_positions["BTCUSDT"] = result["position_opened"]

        # Закрыть остаток позиции если осталась

        if current_positions:

            last_candle = df.iloc[-1]

            for symbol, pos in current_positions.items():

                trade = self.pipeline._close_position(

                    symbol=symbol,

                    position=pos,

                    exit_price=Decimal(str(last_candle["close"])),

                    exit_time=last_candle["timestamp"],

                )

                if trade:

                    trades.append(trade)

            self.pipeline._update_equity_after_trades(trades)

        # Рассчитать метрики

        metrics = self.pipeline.calculate_metrics(

            trades=trades,

            start_time=df.iloc[0]["timestamp"],

            end_time=df.iloc[-1]["timestamp"],

            period_type=period_type,

        )

        return metrics

    def _normalize_signals(self, signals: Any) -> Dict[int, Dict]:
        """Нормализовать сигналы в dict по индексу"""

        if isinstance(signals, dict):

            return signals

        elif isinstance(signals, list):

            # Если список - ассумируем index-matched

            return {i: s for i, s in enumerate(signals) if s}

        else:

            return {}

    def generate_report(

        self,

        train_metrics: Optional[ValidationMetrics],

        test_metrics: Optional[ValidationMetrics],

        forward_metrics: Optional[ValidationMetrics] = None,

        live_metrics: Optional[ValidationMetrics] = None,

    ) -> ValidationReport:
        """

        Генерировать полный report.


        Args:

            train_metrics: Метрики на train данных

            test_metrics: Метрики на test данных (out-of-sample)

            forward_metrics: Метрики на forward данных (опционально)

            live_metrics: Метрики на live данных (опционально)


        Returns:

            ValidationReport

        """

        report = ValidationReport(

            strategy_name=self.strategy_name,

            train_metrics=train_metrics,

            test_metrics=test_metrics,

            forward_metrics=forward_metrics,

            live_metrics=live_metrics,

        )

        # Сравнить train vs test

        if train_metrics and test_metrics:

            report.train_vs_test = self._compare_periods(train_metrics, test_metrics)

        # Валидировать

        report.is_valid, report.warnings, report.errors = self._validate_strategy(

            train_metrics, test_metrics

        )

        return report

    def _compare_periods(

        self,

        period1: ValidationMetrics,

        period2: ValidationMetrics,

    ) -> Dict[str, Any]:
        """Сравнить два периода"""

        comparison = {

            "trades": {

                "train": period1.total_trades,

                "test": period2.total_trades,

                "ratio": (

                    float(period2.total_trades / period1.total_trades)

                    if period1.total_trades > 0

                    else 0

                ),

            },

            "net_pnl": {

                "train": float(period1.net_pnl),

                "test": float(period2.net_pnl),

                "difference": float(period2.net_pnl - period1.net_pnl),

            },

            "win_rate": {

                "train": float(period1.win_rate),

                "test": float(period2.win_rate),

                "difference": float(period2.win_rate - period1.win_rate),

            },

            "profit_factor": {

                "train": float(period1.profit_factor),

                "test": float(period2.profit_factor),

            },

            "max_drawdown": {

                "train": float(period1.max_drawdown_percent),

                "test": float(period2.max_drawdown_percent),

                "difference": float(period2.max_drawdown_percent - period1.max_drawdown_percent),

            },

        }

        return comparison

    def _validate_strategy(

        self,

        train_metrics: Optional[ValidationMetrics],

        test_metrics: Optional[ValidationMetrics],

    ) -> Tuple[bool, List[str], List[str]]:
        """

        Валидировать стратегию.


        Returns:

            (is_valid, warnings, errors)

        """

        warnings = []

        errors = []

        if not test_metrics or test_metrics.total_trades == 0:

            errors.append("No trades on test data")

            return False, warnings, errors

        # Проверка 1: Win rate > 40%

        if test_metrics.win_rate < Decimal("40"):

            warnings.append(f"Low win rate on test: {test_metrics.win_rate:.1f}%")

        # Проверка 2: Profit factor > 1.5

        if test_metrics.profit_factor < Decimal("1.5"):

            warnings.append(f"Low profit factor on test: {test_metrics.profit_factor:.2f}")

        # Проверка 3: Max drawdown < 20%

        if test_metrics.max_drawdown_percent > Decimal("20"):

            warnings.append(f"High max drawdown on test: {test_metrics.max_drawdown_percent:.1f}%")

        # Проверка 4: Test vs Train - не должно быть катастрофического перепада

        if train_metrics and test_metrics:

            train_vs_test_ratio = (

                float(test_metrics.net_pnl / train_metrics.net_pnl)

                if train_metrics.net_pnl != 0

                else 0

            )

            if train_vs_test_ratio < 0.5:  # Test performance < 50% от train

                warnings.append(

                    f"Significant performance degradation in test: {train_vs_test_ratio:.1%}"

                )

        is_valid = len(errors) == 0

        return is_valid, warnings, errors

    def export_report(self, report: ValidationReport, filepath: str) -> None:
        """

        Экспортировать report в JSON.


        Args:

            report: ValidationReport

            filepath: Путь для сохранения

        """

        data = {

            "strategy_name": report.strategy_name,

            "timestamp": report.timestamp.isoformat(),

            "is_valid": report.is_valid,

            "warnings": report.warnings,

            "errors": report.errors,

        }

        if report.train_metrics:

            data["train"] = {

                "total_trades": report.train_metrics.total_trades,

                "winning_trades": report.train_metrics.winning_trades,

                "losing_trades": report.train_metrics.losing_trades,

                "net_pnl": float(report.train_metrics.net_pnl),

                "gross_pnl": float(report.train_metrics.gross_pnl),

                "total_commission": float(report.train_metrics.total_commission),

                "total_slippage": float(report.train_metrics.total_slippage),

                "win_rate": float(report.train_metrics.win_rate),

                "profit_factor": float(report.train_metrics.profit_factor),

                "expectancy": float(report.train_metrics.expectancy),

                "max_drawdown_usd": float(report.train_metrics.max_drawdown_usd),

                "max_drawdown_percent": float(report.train_metrics.max_drawdown_percent),

            }

        if report.test_metrics:

            data["test"] = {

                "total_trades": report.test_metrics.total_trades,

                "winning_trades": report.test_metrics.winning_trades,

                "losing_trades": report.test_metrics.losing_trades,

                "net_pnl": float(report.test_metrics.net_pnl),

                "gross_pnl": float(report.test_metrics.gross_pnl),

                "total_commission": float(report.test_metrics.total_commission),

                "total_slippage": float(report.test_metrics.total_slippage),

                "win_rate": float(report.test_metrics.win_rate),

                "profit_factor": float(report.test_metrics.profit_factor),

                "expectancy": float(report.test_metrics.expectancy),

                "max_drawdown_usd": float(report.test_metrics.max_drawdown_usd),

                "max_drawdown_percent": float(report.test_metrics.max_drawdown_percent),

            }

        if report.train_vs_test:

            data["train_vs_test_comparison"] = {k: v for k, v in report.train_vs_test.items()}

        with open(filepath, "w") as f:

            json.dump(data, f, indent=2, default=str)

        logger.info(f"Report exported to {filepath}")
