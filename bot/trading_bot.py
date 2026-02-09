"""

Trading Bot: главный класс для paper и live режимов.


Объединяет:

- Data feeds (REST/WS)

- Feature pipeline

- Strategies + Meta-layer

- Risk engine

- Execution engine

- Instrument rules (price/qty normalization)

"""


import time

from typing import Dict, Any, Optional

from decimal import Decimal

from storage.database import Database

from exchange.market_data import MarketDataClient

from exchange.account import AccountClient

from exchange.instruments import InstrumentsManager, normalize_order

from storage.position_state import PositionStateManager

from execution.stop_loss_tp_manager import StopLossTakeProfitManager, StopLossTPConfig

from execution.position_signal_handler import (

    PositionSignalHandler,

    SignalActionConfig,

    SignalAction,

)

from execution.kill_switch import KillSwitchManager

from execution.paper_trading_simulator import PaperTradingSimulator, PaperTradingConfig

from execution.trade_metrics import TradeMetricsCalculator, EquityCurve

from data.features import FeaturePipeline

from strategy.meta_layer import MetaLayer

from risk import PositionSizer, RiskLimits, CircuitBreaker, KillSwitch

from risk.advanced_risk_limits import AdvancedRiskLimits, RiskLimitsConfig, RiskDecision

from risk.volatility_position_sizer import VolatilityPositionSizer, VolatilityPositionSizerConfig

from risk.risk_monitor import RiskMonitorService, RiskMonitorConfig

from execution import OrderManager, PositionManager

from utils import retry_api_call

from logger import setup_logger

from signal_logger import get_signal_logger

from config.settings import ConfigManager


logger = setup_logger(__name__)

signal_logger = get_signal_logger()


class TradingBot:

    """Главный класс торгового бота"""

    def __init__(

        self,

        mode: str,  # 'paper' или 'live'

        strategies: list,

        symbol: str = "BTCUSDT",

        testnet: bool = True,

        config: Optional[ConfigManager] = None,

    ):
        """

        Args:

            mode: Режим работы ('paper' или 'live')

            strategies: Список стратегий

            symbol: Торговый символ

            testnet: Использовать testnet

            config: ConfigManager для параметров из JSON (опционально)

        """

        self.mode = mode

        self.symbol = symbol

        self.testnet = testnet

        self.is_running = False

        # Инициализируем конфиг (используем переданный или создаём новый)

        self.config = config or ConfigManager()

        logger.info(f"[TradingBot Risk Config] Loading risk parameters from config")

        # Инициализация компонентов

        logger.info(f"Initializing TradingBot in {mode.upper()} mode...")

        self.db = Database()

        self.market_client = MarketDataClient(testnet=testnet)

        self.account_client = AccountClient(testnet=testnet)

        # Для live режима создаём REST клиент один раз и используем для всех компонентов

        if mode == "live":

            from exchange.base_client import BybitRestClient

            rest_client = BybitRestClient(testnet=testnet)

            # Устанавливаем leverage из конфига
            try:
                lev = str(int(float(self.config.get("risk_management.max_leverage", 10))))
                self.account_client.set_leverage(category="linear", symbol=self.symbol, buy_leverage=lev, sell_leverage=lev)
                logger.info(f"[CONFIG] set_leverage applied: {self.symbol} -> {lev}x")
            except Exception as e:
                logger.warning(f"[CONFIG] set_leverage failed for {self.symbol}: {e}")

        # Инициализируем менеджер инструментов для нормализации ордеров

        if mode == "live":

            self.instruments_manager = InstrumentsManager(rest_client, category="linear")

            # Загружаем информацию об инструментах при старте

            if not self.instruments_manager.load_instruments():

                logger.warning("Failed to load instruments info")

        else:

            self.instruments_manager = None

        # Инициализируем менеджер состояния позиции для отслеживания и синхронизации с биржей

        if mode == "live":

            self.position_state_manager = PositionStateManager(self.account_client, symbol)

            logger.info(f"Position state manager initialized for {symbol}")

        else:

            self.position_state_manager = None

        # ВАЖНО: Сначала создаём OrderManager и PositionManager (до SL/TP manager)

        if mode == "live":

            self.order_manager = OrderManager(rest_client, self.db)

            self.position_manager = PositionManager(self.order_manager)

            logger.info("Order manager and position manager initialized")

        else:

            self.order_manager = None

            self.position_manager = None

        # Инициализируем менеджер SL/TP с привязкой к ATR (требует order_manager)

        if mode == "live":

            # Конфигурируем SL/TP на основе волатильности - ПАРАМЕТРЫ ИЗ КОНФИГА

            sl_tp_config = StopLossTPConfig(

                sl_atr_multiplier=self.config.get("stop_loss_tp.sl_atr_multiplier", 1.5),

                tp_atr_multiplier=self.config.get("stop_loss_tp.tp_atr_multiplier", 2.0),

                sl_percent_fallback=self.config.get("stop_loss_tp.sl_percent_fallback", 1.0),

                tp_percent_fallback=self.config.get("stop_loss_tp.tp_percent_fallback", 2.0),

                use_exchange_sl_tp=self.config.get("stop_loss_tp.use_exchange_sl_tp", True),

                use_virtual_levels=self.config.get("stop_loss_tp.use_virtual_levels", True),

                enable_trailing_stop=self.config.get("stop_loss_tp.enable_trailing_stop", True),

            )

            self.sl_tp_manager = StopLossTakeProfitManager(self.order_manager, sl_tp_config)

            logger.info(f"SL/TP manager initialized: sl_atr={sl_tp_config.sl_atr_multiplier}, tp_atr={sl_tp_config.tp_atr_multiplier}")

        else:

            self.sl_tp_manager = None

        # Kill Switch Manager (для аварийного закрытия)

        if mode == "live":

            # Получаем список разрешённых символов из конфигурации
            allowed_symbols = [symbol] if symbol else []  # Используем текущий symbol из конфига

            self.kill_switch_manager = KillSwitchManager(
                client=rest_client,
                order_manager=self.order_manager,
                db=self.db,
                allowed_symbols=allowed_symbols,
            )

            logger.info("Kill switch manager initialized for emergency shutdown")

        else:

            self.kill_switch_manager = None

        # Advanced Risk Limits (D2 - для проверки leverage/notional/daily_loss/drawdown)
        # ВАЖНО: Создаем ДО RiskMonitorService, т.к. он использует этот компонент
        if mode == "live":
            risk_config = RiskLimitsConfig(
                max_leverage=Decimal(str(self.config.get("risk_management.max_leverage", 10))),
                max_notional=Decimal(str(self.config.get("risk_management.max_notional", 50000))),
                daily_loss_limit_percent=Decimal(str(self.config.get("risk_management.daily_loss_limit_percent", 5))),
                max_drawdown_percent=Decimal(str(self.config.get("risk_management.max_drawdown_percent", 10))),
            )
            self.advanced_risk_limits = AdvancedRiskLimits(self.db, risk_config)
            logger.info(f"[Advanced Risk Limits] max_leverage={risk_config.max_leverage}, max_notional={risk_config.max_notional}, daily_loss={risk_config.daily_loss_limit_percent}%")
        else:
            self.advanced_risk_limits = None

        # Reconciliation Service (для синхронизации состояния с биржей)
        if mode == "live":
            from execution.reconciliation import ReconciliationService
            
            self.reconciliation_service = ReconciliationService(
                client=rest_client,
                position_manager=self.position_manager,
                db=self.db,
                symbol=symbol,
                reconcile_interval=60,  # Сверка каждые 60 секунд
            )
            logger.info("Reconciliation service initialized")
        else:
            self.reconciliation_service = None

        # Risk Monitor Service (для реал-тайм мониторинга рисков по данным биржи)
        if mode == "live":
            risk_monitor_config = RiskMonitorConfig(
                max_daily_loss_percent=self.config.get("risk_monitor.max_daily_loss_percent", 5.0),
                max_position_notional=self.config.get("risk_monitor.max_position_notional", 50000.0),
                max_leverage=self.config.get("risk_monitor.max_leverage", 10.0),
                max_orders_per_symbol=self.config.get("risk_monitor.max_orders_per_symbol", 10),
                monitor_interval_seconds=self.config.get("risk_monitor.monitor_interval_seconds", 30),
                enable_auto_kill_switch=self.config.get("risk_monitor.enable_auto_kill_switch", True),
            )
            
            self.risk_monitor = RiskMonitorService(
                account_client=self.account_client,
                kill_switch_manager=self.kill_switch_manager,
                advanced_risk_limits=self.advanced_risk_limits,
                db=self.db,
                symbol=symbol,
                config=risk_monitor_config,
            )
            logger.info(f"[Risk Monitor] max_daily_loss={risk_monitor_config.max_daily_loss_percent}%, max_leverage={risk_monitor_config.max_leverage}, interval={risk_monitor_config.monitor_interval_seconds}s")
        else:
            self.risk_monitor = None

        # Инициализируем обработчик сигналов для позиций (flip/add/ignore)

        if mode == "live":

            # Конфигурируем правила для обработки сигналов

            signal_action_config = SignalActionConfig(

                default_action=SignalAction.IGNORE,  # По умолчанию игнорируем конфликты

                long_signal_action=SignalAction.IGNORE,

                short_signal_action=SignalAction.IGNORE,

                # Раскомментируйте для разрешения пирамидинга:

                # long_signal_action=SignalAction.ADD,

                # short_signal_action=SignalAction.ADD,

                # max_pyramid_levels=3,

                # Или для flip:

                # long_signal_action=SignalAction.FLIP,

                # short_signal_action=SignalAction.FLIP,

            )

            self.signal_handler = PositionSignalHandler(signal_action_config)

            logger.info("Signal handler initialized with action config")

        else:

            self.signal_handler = None

        self.pipeline = FeaturePipeline()

        # MetaLayer config (from JSON)
        use_mtf = bool(self.config.get("meta_layer.use_mtf", True))
        mtf_score_threshold = float(self.config.get("meta_layer.mtf_score_threshold", 0.6))
        self.meta_layer = MetaLayer(
            strategies,
            use_mtf=use_mtf,
            mtf_score_threshold=mtf_score_threshold,
        )


        # Risk

        self.position_sizer = PositionSizer()

        # Volatility-scaled Position Sizer (D3)

        if mode == "live":

            volatility_config = VolatilityPositionSizerConfig(

                risk_percent=Decimal(str(self.config.get("risk_management.position_risk_percent", 1.0) / 100)),

                atr_multiplier=Decimal(str(self.config.get("risk_management.atr_multiplier", 2.0))),

                min_position_size=Decimal(str(self.config.get("risk_management.min_position_size", 0.00001))),

                max_position_size=Decimal(str(self.config.get("risk_management.max_position_size", 100.0))),

                use_percent_fallback=True,

                percent_fallback=Decimal(str(self.config.get("risk_management.percent_fallback", 5.0))),

                max_leverage=Decimal(str(self.config.get("risk_management.max_leverage", 10.0))),

            )

            self.volatility_position_sizer = VolatilityPositionSizer(
                volatility_config,
                instruments_manager=self.instruments_manager,
            )

            logger.info(f"[Volatility Sizer] risk_percent={volatility_config.risk_percent}, atr_multiplier={volatility_config.atr_multiplier}")

        else:

            self.volatility_position_sizer = None

        self.risk_limits = RiskLimits(self.db)

        self.circuit_breaker = CircuitBreaker()

        self.kill_switch = KillSwitch(self.db)

        # Paper mode execution components

        if mode == "paper":

            # Paper mode: используем симуляцию (E1)

            # Инициализируем PaperTradingSimulator

            paper_config = PaperTradingConfig(

                initial_balance=Decimal(str(self.config.get("paper_trading.initial_balance", 10000))),

                maker_commission=Decimal(str(self.config.get("paper_trading.maker_commission", 0.0002))),

                taker_commission=Decimal(str(self.config.get("paper_trading.taker_commission", 0.0004))),

                slippage_buy=Decimal(str(self.config.get("paper_trading.slippage_buy", 0.0001))),

                slippage_sell=Decimal(str(self.config.get("paper_trading.slippage_sell", 0.0001))),

                use_random_slippage=self.config.get("paper_trading.use_random_slippage", False),

                seed=None,  # Для воспроизводимости установить seed

            )

            self.paper_simulator = PaperTradingSimulator(paper_config)

            self.equity_curve = EquityCurve()

            logger.info(f"[Paper Trading] initial_balance=${float(paper_config.initial_balance):.2f}, maker_fee={float(paper_config.maker_commission)*100:.03f}%")

        logger.info("TradingBot initialized successfully")

    def run(self):
        """Главный цикл бота"""

        logger.info(f"Starting bot in {self.mode.upper()} mode...")

        # Проверка kill switch

        if self.kill_switch.check_status():

            logger.error("Kill switch is active! Cannot start. Reset with confirmation first.")

            return

        # Выполняем первоначальную сверку состояния с биржей (для live режима)
        if self.mode == "live" and self.reconciliation_service:
            logger.info("Running initial reconciliation with exchange...")
            try:
                self.reconciliation_service.run_reconciliation()
                logger.info("Initial reconciliation complete")
                
                # Запускаем фоновый поток для периодической сверки
                self.reconciliation_service.start_loop()
            except Exception as e:
                logger.error(f"Initial reconciliation failed: {e}", exc_info=True)
                # Продолжаем работу даже если сверка не удалась

        # Запускаем Risk Monitor для реал-тайм проверки лимитов (для live режима)
        if self.mode == "live" and self.risk_monitor:
            logger.info("Starting risk monitoring...")
            try:
                # Первоначальная проверка лимитов
                initial_check = self.risk_monitor.run_monitoring_check()
                logger.info(f"Initial risk check: decision={initial_check['decision'].value}")
                
                # Если уже критические нарушения - не запускаемся
                if initial_check["decision"] == RiskDecision.STOP:
                    logger.critical("CRITICAL risk violations detected! Cannot start trading.")
                    return
                
                # Запускаем фоновый поток для периодического мониторинга
                self.risk_monitor.start_monitoring()
                logger.info("Risk monitoring started")
            except Exception as e:
                logger.error(f"Risk monitoring setup failed: {e}", exc_info=True)
                # Продолжаем работу даже если мониторинг не удался

        self.is_running = True

        try:

            while self.is_running:

                # 1. Получаем данные

                data = self._fetch_market_data()

                if not data:

                    time.sleep(5)

                    continue

                # 2. Строим фичи

                df_with_features = self.pipeline.build_features(

                    data["d"], orderbook=data.get("orderbook")

                )

                features = data.get("orderflow_features", {})
                
                # TASK-001: Гарантируем наличие symbol в features
                features["symbol"] = self.symbol
                
                # TASK-002: Гарантируем наличие orderflow features в features
                # Orderflow features (spread_percent, depth_imbalance, etc.) вычисляются в build_features()
                # и добавляются в df_with_features, но могут быть потеряны если orderbook_resp был недоступен.
                # Извлекаем их из последней строки df для гарантии наличия.
                import pandas as pd
                latest_row = df_with_features.iloc[-1]
                for key in ["spread_percent", "depth_imbalance", "liquidity_concentration", "midprice"]:
                    if key not in features or features.get(key) is None:
                        if key in latest_row.index and pd.notna(latest_row[key]):
                            features[key] = float(latest_row[key])
                        else:
                            # Fallback значения если нет в df
                            if key == "spread_percent":
                                features[key] = 0.01  # Оптимистичное значение по умолчанию
                            elif key == "depth_imbalance":
                                features[key] = 0.0
                            elif key == "liquidity_concentration":
                                features[key] = 0.5
                            elif key == "midprice":
                                features[key] = float(latest_row.get("close", 0))

                # 3. Проверяем circuit breaker

                if not self.circuit_breaker.is_trading_allowed():

                    logger.warning(

                        f"Trading halted by circuit breaker: {self.circuit_breaker.break_reason}"

                    )

                    time.sleep(60)

                    continue

                # 4. Получаем сигнал от стратегий

                # Provide runtime flags to MetaLayer/NoTradeZones
                if not features:
                    features = {}
                features["is_testnet"] = bool(self.testnet)
                features["allow_anomaly_on_testnet"] = bool(self.config.get("meta_layer.allow_anomaly_on_testnet", True))

                signal = self.meta_layer.get_signal(df_with_features, features)

                if signal:

                    # Логируем сгенерированный сигнал

                    signal_logger.log_signal_generated(

                        strategy_name=signal.get("strategy", "Unknown"),

                        symbol=self.symbol,

                        direction=signal.get("signal", "unknown").upper(),

                        confidence=signal.get("confidence", 0),

                        price=signal.get("entry_price", 0),

                        reasons=signal.get("reasons", []),

                        values=signal.get("values", {}),

                    )

                    self._process_signal(signal)

                else:

                    # Логируем отладочную информацию - нет сигналов

                    signal_logger.log_debug_info(

                        category="market_analysis",

                        symbol=self.symbol,

                        last_close=float(df_with_features.iloc[-1]["close"]),

                        no_signal_reason="No strategy triggered",

                    )

                # 5. Обновляем метрики

                self._update_metrics()

                # 6. Проверяем SL/TP уровни и виртуальные триггеры (если в live mode)

                if self.mode == "live" and self.sl_tp_manager and data.get("d") is not None:

                    current_price = Decimal(str(data["d"].iloc[-1]["close"]))

                    current_atr = data["d"].iloc[-1].get("atr")

                    # Проверяем все активные позиции на SL/TP триггеры

                    for (

                        position_id,

                        sl_tp_levels,

                    ) in self.sl_tp_manager.get_all_active_levels().items():

                        # Проверяем виртуальные уровни

                        triggered, trigger_type = self.sl_tp_manager.check_virtual_levels(

                            position_id=position_id,

                            current_price=current_price,

                            current_qty=sl_tp_levels.entry_qty,

                        )

                        if triggered:

                            # SL или TP триггернут - нужно закрыть позицию

                            logger.warning(

                                f"SL/TP triggered: {trigger_type.upper()} for {position_id} "

                                f"@ {current_price} (SL={sl_tp_levels.sl_price}, TP={sl_tp_levels.tp_price})"

                            )

                            # TODO: Выполнить market close ордер

                            self.sl_tp_manager.close_position_levels(position_id)

                        # Обновляем trailing stop при благоприятном ценовом движении

                        if current_atr:

                            self.sl_tp_manager.update_trailing_stop(

                                position_id=position_id,

                                current_price=current_price,

                            )

                # 6a. Проверяем SL/TP для paper mode (E1)

                if self.mode == "paper" and data.get("d") is not None:

                    current_price = Decimal(str(data["d"].iloc[-1]["close"]))

                    # Обновить цены позиций

                    self.paper_simulator.update_market_prices({self.symbol: current_price})

                    # Проверить SL/TP триггеры

                    triggered = self.paper_simulator.check_sl_tp(current_price)

                    for symbol, trigger_type in triggered.items():

                        # Закрыть позицию по SL/TP

                        success, msg = self.paper_simulator.close_position_on_trigger(

                            symbol=symbol,

                            trigger_type=trigger_type,

                            exit_price=current_price,

                        )

                        if success:

                            logger.info(f"Paper: Position closed by {trigger_type.upper()}: {msg}")

                            # Записать в БД

                            self.db.save_signal(

                                strategy="SL/TP",

                                symbol=symbol,

                                signal_type=f"close_{trigger_type}",

                                price=float(current_price),

                                metadata={"trigger": trigger_type},

                            )

                    # Записать точку на equity curve

                    equity = self.paper_simulator.get_equity()

                    self.equity_curve.add_point(time.time(), equity)

                # 7. Синхронизируем состояние позиции с биржей (если в live mode)

                if self.mode == "live" and self.position_state_manager:

                    if self.position_state_manager.has_position():

                        sync_success = self.position_state_manager.sync_with_exchange()

                        if not sync_success:

                            logger.warning("Position state sync failed")

                        # Проверяем валидность позиции (критические ошибки)

                        is_valid, error_msg = self.position_state_manager.validate_position()

                        if not is_valid:

                            logger.error(f"Position validation failed: {error_msg}")

                            # Закрываем позицию если есть критические ошибки

                            self.position_state_manager.close_position()

                # Пауза перед следующей итерацией

                time.sleep(10)  # 10 секунд

        except KeyboardInterrupt:

            logger.info("\n🛑 Received stop signal, shutting down...")

            self.stop()

        except Exception as e:

            logger.error(f"Critical error in main loop: {e}", exc_info=True)

            # Activate kill switch for emergency shutdown

            if self.mode == "live" and self.kill_switch_manager:

                logger.critical("Activating emergency kill switch due to critical error!")

                result = self.kill_switch_manager.activate(f"Critical error: {str(e)}")

                if result["success"]:

                    logger.critical(

                        f"Emergency shutdown complete: {result['orders_cancelled']} orders cancelled, "

                        f"{result['positions_closed']} positions closed"

                    )

            else:

                self.kill_switch.activate(f"Critical error: {str(e)}")

            self.stop()

    def _fetch_market_data(self) -> Optional[Dict[str, Any]]:
        """Получить рыночные данные с retry logic для всех данных"""

        try:

            import pandas as pd

            # Главный таймфрейм - 1h

            kline_interval = str(self.config.get("market_data.kline_interval", "60"))
            kline_limit = int(self.config.get("market_data.kline_limit", 500))

            try:

                kline_resp = retry_api_call(

                    self.market_client.get_kline,

                    self.symbol,

                    interval=kline_interval,

                    limit=kline_limit,

                    max_retries=2,

                )

            except Exception as e:

                logger.error(f"Kline retry failed: {e}", exc_info=True)

                return None

            if not kline_resp or kline_resp.get("retCode") != 0:

                logger.warning(f"Failed to fetch kline data: {kline_resp}")

                return None

            candles = kline_resp.get("result", {}).get("list", [])

            if not candles:

                logger.warning("No kline candles received")

                return None

            df = pd.DataFrame(

                candles,

                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],

            )

            for col in ["open", "high", "low", "close", "volume"]:

                df[col] = df[col].astype(float)

            # Sort by timestamp and set as DatetimeIndex for VWAP calculation
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
            df = df.sort_values("timestamp").set_index("timestamp")

            logger.debug(f"Loaded {len(df)} candles for 1h timeframe")

            # Загрузить данные для других таймфреймов в кэш (для MTF)

            if self.meta_layer.use_mtf and self.meta_layer.timeframe_cache:

                timeframes = [("1", "1m"), ("5", "5m"), ("15", "15m"), ("240", "4h")]

                for interval, tf_name in timeframes:

                    try:

                        tf_resp = retry_api_call(

                            self.market_client.get_kline,

                            self.symbol,

                            interval=interval,

                            limit=100,

                            max_retries=1,

                        )

                        if tf_resp and tf_resp.get("retCode") == 0:

                            tf_candles = tf_resp.get("result", {}).get("list", [])

                            if tf_candles:

                                # Добавить последнюю свечу в кэш

                                last_candle = tf_candles[0]

                                candle_dict = {

                                    "timestamp": last_candle[0],

                                    "open": float(last_candle[1]),

                                    "high": float(last_candle[2]),

                                    "low": float(last_candle[3]),

                                    "close": float(last_candle[4]),

                                    "volume": float(last_candle[5]),

                                }

                                self.meta_layer.timeframe_cache.add_candle(interval, candle_dict)

                                logger.debug(

                                    f"Loaded {len(tf_candles)} candles for {tf_name} timeframe"

                                )

                        else:

                            logger.debug(f"Failed to fetch {tf_name} data")

                    except Exception as e:

                        logger.debug(f"Error fetching {tf_name} data: {e}")

            else:

                logger.debug("MTF disabled or cache not available")

            # Orderbook с retry

            orderbook_resp = retry_api_call(

                self.market_client.get_orderbook, self.symbol, limit=50, max_retries=2

            )

            orderbook = None

            orderflow_features = {}

            if orderbook_resp and orderbook_resp.get("retCode") == 0:

                result = orderbook_resp.get("result", {})

                orderbook = {"bids": result.get("b", []), "asks": result.get("a", [])}

                orderflow_features = self.pipeline.calculate_orderflow_features(orderbook)

            # Деривативные данные с retry logic (могут быть rate limits)

            derivatives_data = {}

            # Mark price с retry

            mark_resp = retry_api_call(

                self.market_client.get_mark_price_kline,

                self.symbol,

                interval="1",

                limit=1,

                max_retries=2,

            )

            if mark_resp and mark_resp.get("retCode") == 0:

                mark_list = mark_resp.get("result", {}).get("list", [])

                if mark_list:

                    try:

                        mark_price = float(mark_list[0][1])

                        derivatives_data["mark_price"] = mark_price

                    except (IndexError, ValueError):

                        pass

            # Index price с retry

            index_resp = retry_api_call(

                self.market_client.get_index_price_kline,

                self.symbol,

                interval="1",

                limit=1,

                max_retries=2,

            )

            if index_resp and index_resp.get("retCode") == 0:

                index_list = index_resp.get("result", {}).get("list", [])

                if index_list:

                    try:

                        index_price = float(index_list[0][1])

                        derivatives_data["index_price"] = index_price

                    except (IndexError, ValueError):

                        pass

            # Open Interest с retry

            oi_resp = retry_api_call(

                self.market_client.get_open_interest,

                self.symbol,

                interval="5min",

                limit=1,

                max_retries=2,

            )

            if oi_resp and oi_resp.get("retCode") == 0:

                oi_list = oi_resp.get("result", {}).get("openInterestList", [])

                if oi_list:

                    try:

                        oi_value = float(oi_list[0][1])

                        derivatives_data["open_interest"] = oi_value

                        derivatives_data["oi_change"] = 0

                    except (IndexError, ValueError):

                        pass

            # Funding Rate с retry

            fr_resp = retry_api_call(

                self.market_client.get_funding_rate_history, self.symbol, limit=1, max_retries=2

            )

            if fr_resp and fr_resp.get("retCode") == 0:

                fr_list = fr_resp.get("result", {}).get("list", [])

                if fr_list:

                    try:

                        fr_item = fr_list[0]

                        # funding rate может быть в разных полях в зависимости от API

                        if isinstance(fr_item, dict):

                            funding_rate = float(fr_item.get("fundingRate", 0))

                        else:

                            # Если это список/кортеж, то индекс 2

                            funding_rate = float(fr_item[2])

                        derivatives_data["funding_rate"] = funding_rate

                    except (IndexError, ValueError, TypeError, KeyError) as e:

                        logger.debug(f"Failed to parse funding rate: {e}")

            self.circuit_breaker.update_data_timestamp()

            return {

                "d": df,

                "orderbook": orderbook,

                "orderflow_features": orderflow_features,

                "derivatives_data": derivatives_data,

            }

        except Exception as e:

            logger.error(f"Failed to fetch market data: {e}", exc_info=True)

            return None

    def _process_signal(self, signal: Dict[str, Any]):
        """Обработать торговый сигнал"""

        logger.info(f"Processing signal: {signal['signal']} from {signal.get('strategy')}")

        # Логируем что сигнал принят

        signal_logger.log_signal_accepted(

            strategy_name=signal.get("strategy", "Unknown"),

            symbol=self.symbol,

            direction=signal.get("signal", "unknown").upper(),

            confidence=signal.get("confidence", 0),

        )

        # В paper mode используем симулятор (E1)

        if self.mode == "paper":

            try:

                # Вычислить размер позиции (используем volatility sizer если есть)

                account_balance = self.paper_simulator.get_account_summary()["equity"]

                qty = None

                atr = signal.get("atr", None)

                if self.volatility_position_sizer and atr:

                    atr_decimal = Decimal(str(atr))

                    try:

                        qty_vol, _ = self.volatility_position_sizer.calculate_position_size(

                            account=Decimal(str(account_balance)),

                            entry_price=Decimal(str(signal["entry_price"])),

                            atr=atr_decimal,

                            signal=signal.get("signal", "long"),
                            
                            symbol=self.symbol,

                        )

                        qty = float(qty_vol)

                    except Exception as e:

                        logger.warning(f"Volatility sizing failed: {e}")

                if qty is None:

                    # Fallback: 1% от equity

                    qty = float(

                        Decimal(str(account_balance))

                        * Decimal("0.01")

                        / Decimal(str(signal["entry_price"]))

                    )

                if qty <= 0:

                    logger.warning("Position size too small for paper trading")

                    return

                # Отправить market ордер в симулятор

                side = "Buy" if signal["signal"] == "long" else "Sell"

                order_id, success, msg = self.paper_simulator.submit_market_order(

                    symbol=self.symbol,

                    side=side,

                    qty=Decimal(str(qty)),

                    current_price=Decimal(str(signal["entry_price"])),

                )

                if not success:

                    logger.warning(f"Paper trading order failed: {msg}")

                    return

                # Установить SL/TP если они есть в сигнале

                if signal.get("stop_loss") and signal.get("take_profit"):

                    self.paper_simulator.set_stop_loss_take_profit(

                        symbol=self.symbol,

                        stop_loss=Decimal(str(signal["stop_loss"])),

                        take_profit=Decimal(str(signal["take_profit"])),

                    )

                # Записать сигнал в БД

                self.db.save_signal(

                    strategy=signal.get("strategy", "Unknown"),

                    symbol=self.symbol,

                    signal_type=signal["signal"],

                    price=signal["entry_price"],

                    metadata={**signal, "order_id": order_id, "qty": qty, "mode": "paper"},

                )

                logger.info(

                    f"[PAPER] {side} {qty:.6f} {self.symbol} @ ${float(signal['entry_price']):.2f}, "

                    f"equity: ${float(account_balance):.2f}"

                )

            except Exception as e:

                logger.error(f"Paper trading error: {e}", exc_info=True)

        else:

            # Live mode: реально открываем позицию

            try:

                # 1. Получаем баланс аккаунта

                balance_result = self.account_client.get_wallet_balance(coin="USDT")

                account_balance = balance_result.get("balance", 0)

                if account_balance <= 0:

                    logger.error(f"Invalid account balance: {account_balance}")

                    return

                # D2: Проверяем риск-лимиты перед открытием позиции

                if self.mode == "live" and self.advanced_risk_limits:

                    # Собираем состояние для risk evaluation

                    current_pos = (

                        self.position_state_manager.get_position()

                        if self.position_state_manager

                        and self.position_state_manager.has_position()

                        else None

                    )

                    current_notional = Decimal("0")

                    current_leverage = Decimal("1")

                    if current_pos:

                        current_notional = Decimal(str(current_pos.qty)) * Decimal(

                            str(signal.get("entry_price", 0))

                        )

                        current_leverage = (

                            Decimal(str(current_pos.qty))

                            * Decimal(str(signal.get("entry_price", 0)))

                            / Decimal(str(account_balance))

                        )

                    # Предполагаемый размер новой позиции

                    new_position_notional = Decimal(str(signal.get("position_size", 0))) * Decimal(

                        str(signal.get("entry_price", 0))

                    )

                    # Получаем текущий realized PnL за день

                    realized_pnl_today = Decimal("0")  # TODO: Get from trade journal

                    # Текущий equity

                    current_equity = Decimal(str(account_balance))  # TODO: Add unrealized PnL

                    risk_state = {

                        "account_balance": Decimal(str(account_balance)),

                        "open_position_notional": current_notional,

                        "position_leverage": current_leverage,

                        "new_position_notional": new_position_notional,

                        "realized_pnl_today": realized_pnl_today,

                        "current_equity": current_equity,

                    }

                    # Evaluate risk

                    risk_decision, risk_details = self.advanced_risk_limits.evaluate(risk_state)

                    logger.info(

                        f"Risk evaluation: {risk_decision.value.upper()} - {risk_details['reason']}"

                    )

                    if risk_decision == RiskDecision.DENY:

                        logger.warning(f"Trade blocked by risk limits: {risk_details['reason']}")

                        # Log structured rejection with risk violation details

                        signal_logger.log_signal_rejected(

                            strategy_name=signal.get("strategy", "Unknown"),

                            symbol=self.symbol,

                            direction=signal.get("signal", "unknown").upper(),

                            confidence=signal.get("confidence", 0),

                            reasons=["risk_limit_violation"],

                            values={

                                "violations": [

                                    {

                                        "check": v.check_name,

                                        "current": float(v.current_value),

                                        "limit": float(v.limit_value),

                                    }

                                    for v in risk_details.get("violations", [])

                                ],

                                "reason": risk_details.get("reason", ""),

                            },

                        )

                        signal_logger.log_debug_info(

                            category="trade_blocked_risk",

                            symbol=self.symbol,

                            reason=risk_details["reason"],

                        )

                        return

                    elif risk_decision == RiskDecision.STOP:

                        logger.critical(

                            f"CRITICAL RISK VIOLATION - Triggering kill switch: {risk_details['reason']}"

                        )

                        # Log critical risk rejection

                        signal_logger.log_signal_rejected(

                            strategy_name=signal.get("strategy", "Unknown"),

                            symbol=self.symbol,

                            direction=signal.get("signal", "unknown").upper(),

                            confidence=signal.get("confidence", 0),

                            reasons=["critical_risk_violation"],

                            values={

                                "violations": [

                                    {

                                        "check": v.check_name,

                                        "current": float(v.current_value),

                                        "limit": float(v.limit_value),

                                        "severity": v.severity,

                                    }

                                    for v in risk_details.get("violations", [])

                                ],

                                "reason": risk_details.get("reason", ""),

                            },

                        )

                        if self.kill_switch_manager:

                            result = self.kill_switch_manager.activate(

                                reason=f"Risk violation: {risk_details['reason']}"

                            )

                            logger.critical(

                                f"Kill switch activated: {result['orders_cancelled']} orders cancelled, "

                                f"{result['positions_closed']} positions closed"

                            )

                        return

                # 0. Проверяем текущую позицию и определяем действие (flip/add/ignore)

                current_pos = (

                    self.position_state_manager.get_position()

                    if self.position_state_manager.has_position()

                    else None

                )

                if current_pos:

                    # Есть открытая позиция - проверяем что делать с новым сигналом

                    signal_action_result = self.signal_handler.handle_signal(

                        current_position={

                            "symbol": current_pos.symbol,

                            "side": current_pos.side,

                            "qty": current_pos.qty,

                            "entry_price": current_pos.entry_price,

                            "pyramid_level": 1,  # TODO: track pyramid level in position state

                        },

                        new_signal=signal,

                        current_price=Decimal(str(signal.get("entry_price", 0))),

                        account_balance=Decimal(str(account_balance)),

                    )

                    if not signal_action_result.success:

                        logger.warning(f"Signal rejected: {signal_action_result.message}")

                        # Log position handler rejection

                        signal_logger.log_signal_rejected(

                            strategy_name=signal.get("strategy", "Unknown"),

                            symbol=self.symbol,

                            direction=signal.get("signal", "unknown").upper(),

                            confidence=signal.get("confidence", 0),

                            reasons=["signal_handler_conflict"],

                            values={

                                "action": signal_action_result.action_taken.value,

                                "message": signal_action_result.message,

                            },

                        )

                        signal_logger.log_debug_info(

                            category="signal_rejected",

                            symbol=self.symbol,

                            reason=signal_action_result.message,

                        )

                        return

                    action = signal_action_result.action_taken

                    if action == SignalAction.IGNORE:

                        logger.warning(f"Signal IGNORED: {signal_action_result.message}")

                        return

                    elif action == SignalAction.ADD:

                        logger.info(f"ADD (pyramid) action: {signal_action_result.message}")

                        # TODO: Implement ADD logic

                        return

                    elif action == SignalAction.FLIP:

                        logger.info(f"FLIP action: {signal_action_result.message}")

                        # TODO: Implement FLIP logic (close current, open opposite)

                        return

                # 2. Расчитаем размер позиции (D3: используем volatility-scaled sizing)

                qty = None

                # Try volatility-scaled sizer first (D3)

                if self.mode == "live" and self.volatility_position_sizer:

                    atr = signal.get("atr", None)

                    if atr:

                        atr_decimal = Decimal(str(atr))

                        try:

                            qty_vol, details_vol = (

                                self.volatility_position_sizer.calculate_position_size(

                                    account=Decimal(str(account_balance)),

                                    entry_price=Decimal(str(signal["entry_price"])),

                                    atr=atr_decimal,

                                    signal=signal.get("signal", "long"),
                                    
                                    symbol=self.symbol,

                                )

                            )

                            qty = qty_vol

                            # STR-001 DoD: Логируем atr, stop, take, risk_usd, qty, stop_distance

                            stop_distance = details_vol.get("distance_to_sl", 0)

                            take_profit_distance = abs(

                                signal.get("take_profit", 0) - signal.get("entry_price", 0)

                            )

                            logger.info(

                                "[STR-001] Volatility-scaled sizing: "

                                f"ATR={atr:.2f}, "

                                f"Stop={signal.get('stop_loss', 0):.2f}, "

                                f"Take={signal.get('take_profit', 0):.2f}, "

                                f"StopDist={stop_distance:.2f}, "

                                f"TakeDist={take_profit_distance:.2f}, "

                                f"Risk=${details_vol['risk_usd']:.2f}, "

                                f"Qty={float(qty):.6f}"

                            )

                            # Записываем в signal_logger для structured logging

                            signal_logger.log_debug_info(

                                category="position_sizing",

                                symbol=self.symbol,

                                atr=atr,

                                stop_loss=signal.get("stop_loss", 0),

                                take_profit=signal.get("take_profit", 0),

                                stop_distance=stop_distance,

                                take_profit_distance=take_profit_distance,

                                risk_usd=details_vol["risk_usd"],

                                qty=float(qty),

                                method="volatility_scaled",

                            )

                        except Exception as e:

                            logger.warning(

                                f"Volatility sizing failed: {e}, falling back to legacy sizer"

                            )

                            qty = None

                # Fallback to legacy sizer

                if qty is None:

                    position_info = self.position_sizer.calculate_position_size(

                        account_balance=account_balance,

                        entry_price=signal["entry_price"],

                        stop_loss_price=signal["stop_loss"],

                        side="Buy" if signal["signal"] == "long" else "Sell",

                    )

                    if not position_info.get("success", False):

                        logger.warning(f"Position sizing failed: {position_info.get('error')}")

                        return

                    qty = position_info.get("position_size", 0)

                    # STR-001 DoD: Логируем для legacy sizer тоже

                    stop_distance = position_info.get("stop_distance", 0)

                    take_profit_distance = abs(

                        signal.get("take_profit", 0) - signal.get("entry_price", 0)

                    )

                    logger.info(

                        "[STR-001] Legacy sizing: "

                        f"Stop={signal.get('stop_loss', 0):.2f}, "

                        f"Take={signal.get('take_profit', 0):.2f}, "

                        f"StopDist={stop_distance:.2f}, "

                        f"TakeDist={take_profit_distance:.2f}, "

                        f"Risk=${position_info.get('risk_amount', 0):.2f}, "

                        f"Qty={float(qty):.6f}"

                    )

                if qty <= 0:

                    logger.warning("Position size too small, skipping trade")

                    return

                # 3. Нормализуем ордер согласно instrument rules (tickSize, qtyStep, минималы)

                # Execution config: Market/Limit (default: Market)
                desired_order_type = str(self.config.get("execution.order_type", "Market") or "Market").strip().lower()
                order_type = "Limit" if desired_order_type in ("limit", "lmt") else "Market"

                # If Limit: try to use strategy-provided target price; fallback to entry_price
                price_for_order = float(signal.get("target_price") or signal.get("entry_price"))

                logger.debug(f"Normalizing order: type={order_type}, price={price_for_order}, qty={qty}")

                normalized_price, normalized_qty, is_valid, norm_message = normalize_order(
                    self.instruments_manager,
                    self.symbol,
                    price_for_order,
                    qty,
                )



                if not is_valid:

                    logger.warning(f"Order normalization failed: {norm_message}")

                    return

                # Логируем нормализованные значения для отладки

                if float(normalized_price) != float(price_for_order) or float(normalized_qty) != qty:

                    logger.info(

                        "Order normalized: "

                        f"price {price_for_order} → {normalized_price}, "

                        f"qty {qty} → {normalized_qty}"

                    )

                else:

                    logger.debug("Order already normalized correctly")

                # 4. Проверяем риск-лимиты

                proposed_trade = {

                    "symbol": self.symbol,

                    "size": float(normalized_qty),

                    "value": float(normalized_qty * normalized_price),

                }

                limits_check = self.risk_limits.check_limits(

                    account_balance=account_balance,

                    proposed_trade=proposed_trade,

                )

                if not limits_check.get("allowed", False):

                    logger.warning(

                        f"Trade rejected by risk limits: {limits_check.get('violations')}"

                    )

                    return

                # 5. Выставляем ордер с нормализованными значениями

                side = "Buy" if signal["signal"] == "long" else "Sell"

                # Генерируем стабильный orderLinkId для идемпотентности
                from execution.order_idempotency import generate_order_link_id
                
                order_link_id = generate_order_link_id(
                    strategy=signal.get("strategy", "default"),
                    symbol=self.symbol,
                    timestamp=int(time.time()),
                    side=signal["signal"],  # "long" или "short"
                    bucket_seconds=60,  # 1 минута - повторы в этом окне используют тот же ID
                )
                
                logger.info(f"Generated orderLinkId: {order_link_id}")
                # time_in_force / postOnly mapping
                time_in_force = str(self.config.get("execution.time_in_force", "GTC") or "GTC")
                post_only = bool(self.config.get("execution.post_only", False))
                if order_type == "Limit" and post_only:
                    time_in_force = "PostOnly"

                order_result = self.order_manager.create_order(
                    category="linear",
                    symbol=self.symbol,
                    side=side,
                    order_type=order_type,
                    qty=float(normalized_qty),  # Используем нормализованное количество
                    price=float(normalized_price) if order_type == "Limit" else None,
                    time_in_force=time_in_force,
                    order_link_id=order_link_id,
                )

                # order_result теперь OrderResult, проверяем success вместо retCode
                if order_result.success:

                    order_id = order_result.order_id

                    logger.info(f"[LIVE] Order placed: {order_id}")

                    # 6. Регистрируем позицию в PositionStateManager для отслеживания

                    side_long = "Long" if signal["signal"] == "long" else "Short"

                    self.position_state_manager.open_position(

                        side=side_long,

                        qty=Decimal(str(normalized_qty)),

                        entry_price=Decimal(str(normalized_price)),

                        order_id=order_id,

                        strategy_id=signal.get("strategy", "Unknown"),

                    )

                    logger.info(

                        "Position registered in state manager: "

                        f"{side_long} {normalized_qty} @ {normalized_price}, orderId={order_id}"

                    )

                    # 7. Рассчитываем и выставляем SL/TP уровни на основе ATR

                    sl_tp_levels = None

                    current_atr = signal.get("atr")

                    if self.sl_tp_manager and current_atr is not None:

                        sl_tp_levels = self.sl_tp_manager.calculate_levels(

                            position_id=order_id,

                            symbol=self.symbol,

                            side=side_long,

                            entry_price=Decimal(str(normalized_price)),

                            entry_qty=Decimal(str(normalized_qty)),

                            current_atr=Decimal(str(current_atr)) if current_atr else None,

                        )

                        logger.info(

                            "[LIVE] SL/TP levels calculated: "

                            f"SL={sl_tp_levels.sl_price}, TP={sl_tp_levels.tp_price} "

                            f"(ATR={current_atr})"

                        )

                        # Пытаемся выставить SL/TP на бирже (если поддерживается)

                        exchange_success, sl_order_id, tp_order_id = (

                            self.sl_tp_manager.place_exchange_sl_tp(

                                position_id=order_id,

                                category="linear",

                            )

                        )

                        if exchange_success and (sl_order_id or tp_order_id):

                            logger.info(

                                "Exchange SL/TP orders placed: "

                                f"SL={sl_order_id}, TP={tp_order_id}"

                            )

                        else:

                            logger.info(f"Using virtual SL/TP monitoring for {order_id}")

                    # 8. Регистрируем позицию в PositionManager для сопровождения (если используется)

                    if self.position_manager:

                        self.position_manager.register_position(

                            symbol=self.symbol,

                            side=side,

                            entry_price=float(normalized_price),

                            size=float(normalized_qty),

                            stop_loss=(

                                float(sl_tp_levels.sl_price)

                                if sl_tp_levels

                                else signal["stop_loss"]

                            ),

                            take_profit=(

                                float(sl_tp_levels.tp_price)

                                if sl_tp_levels

                                else signal.get("take_profit")

                            ),

                        )

                    # 8. Обновляем счётчик сделок

                    self.risk_limits.increment_trade_count()

                    # 9. Сохраняем сигнал в БД

                    self.db.save_signal(

                        strategy=signal.get("strategy", "Unknown"),

                        symbol=self.symbol,

                        signal_type=signal["signal"],

                        price=float(normalized_price),

                        metadata=signal,

                    )

                    logger.info(

                        f"Trade executed successfully: {side} {normalized_qty} @ {normalized_price}"

                    )

                else:

                    logger.error(f"Failed to place order: {order_result.error}")

            except Exception as e:

                logger.error(f"Error processing live signal: {e}", exc_info=True)

    def _update_metrics(self):
        """Обновить метрики и equity"""

        pass  # TODO: Реализовать сбор метрик

    def get_paper_trading_report(self) -> Dict[str, Any]:
        """

        Получить отчет paper trading (E1).

        Только для mode == 'paper'.


        Returns:

            Dict с метриками, сделками и equity curve

        """

        if self.mode != "paper" or not hasattr(self, "paper_simulator"):

            return {"error": "Paper trading not active"}

        trades = self.paper_simulator.get_trades()

        account_summary = self.paper_simulator.get_account_summary()

        # Вычислить метрики

        metrics = TradeMetricsCalculator.calculate(

            trades,

            self.paper_simulator.initial_balance,

            self.equity_curve,

        )

        # Получить max drawdown из equity curve

        max_dd_dollars, max_dd_percent = self.equity_curve.get_max_drawdown(

            self.paper_simulator.initial_balance

        )

        return {

            "account": account_summary,

            "trades": [

                {

                    "id": t.trade_id,

                    "symbol": t.symbol,

                    "side": t.side,

                    "entry_price": float(t.entry_price),

                    "exit_price": float(t.exit_price),

                    "qty": float(t.entry_qty),

                    "pnl": float(t.pnl),

                    "pnl_after_commission": float(t.pnl_after_commission),

                    "roi_percent": float(t.roi_percent),

                    "was_sl_hit": t.was_sl_hit,

                    "was_tp_hit": t.was_tp_hit,

                    "duration_seconds": t.duration_seconds,

                }

                for t in trades

            ],

            "metrics": {

                "total_trades": metrics.total_trades,

                "winning_trades": metrics.winning_trades,

                "losing_trades": metrics.losing_trades,

                "win_rate_percent": float(metrics.win_rate),

                "profit_factor": (

                    float(metrics.profit_factor) if metrics.profit_factor != float("in") else None

                ),

                "expectancy": float(metrics.expectancy),

                "avg_pnl_per_trade": float(metrics.avg_pnl_per_trade),

                "largest_win": float(metrics.largest_winning_trade),

                "largest_loss": float(metrics.largest_losing_trade),

                "max_drawdown_dollars": float(metrics.max_drawdown_dollars),

                "max_drawdown_percent": float(metrics.max_drawdown_percent),

                "sharpe_ratio": float(metrics.sharpe_ratio),

                "sortino_ratio": float(metrics.sortino_ratio),

                "recovery_factor": (

                    float(metrics.recovery_factor) if metrics.recovery_factor > 0 else None

                ),

                "sl_hit_rate_percent": float(metrics.sl_hit_rate),

                "tp_hit_rate_percent": float(metrics.tp_hit_rate),

                "total_commission_paid": float(metrics.total_commission_paid),

            },

            "equity_curve": {

                "timestamps": self.equity_curve.timestamps,

                "equity_values": self.equity_curve.equity_values,

                "max_equity": float(self.equity_curve.max_equity),

            },

        }

    def stop(self):
        """Остановить бота"""

        logger.info("Stopping bot...")

        self.is_running = False
        
        # Остановить reconciliation service если запущен
        if self.mode == "live" and self.reconciliation_service:
            self.reconciliation_service.stop_loop()
            logger.info("Reconciliation service stopped")
        
        # Остановить risk monitor если запущен
        if self.mode == "live" and self.risk_monitor:
            self.risk_monitor.stop_monitoring()
            logger.info("Risk monitor stopped")

        logger.info("Bot stopped successfully")
