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
from data.features import FeaturePipeline
from strategy.meta_layer import MetaLayer
from risk import PositionSizer, RiskLimits, CircuitBreaker, KillSwitch
from risk.advanced_risk_limits import AdvancedRiskLimits, RiskLimitsConfig, RiskDecision
from execution import OrderManager, PositionManager
from utils import retry_api_call
from logger import setup_logger
from signal_logger import get_signal_logger

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
    ):
        """
        Args:
            mode: Режим работы ('paper' или 'live')
            strategies: Список стратегий
            symbol: Торговый символ
            testnet: Использовать testnet
        """
        self.mode = mode
        self.symbol = symbol
        self.testnet = testnet
        self.is_running = False

        # Инициализация компонентов
        logger.info(f"Initializing TradingBot in {mode.upper()} mode...")

        self.db = Database()
        self.market_client = MarketDataClient(testnet=testnet)
        self.account_client = AccountClient(testnet=testnet)

        # Инициализируем менеджер инструментов для нормализации ордеров
        if mode == "live":
            from exchange.base_client import BybitRestClient
            rest_client = BybitRestClient(testnet=testnet)
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

        # Инициализируем менеджер SL/TP с привязкой к ATR
        if mode == "live":
            # Конфигурируем SL/TP на основе волатильности
            sl_tp_config = StopLossTPConfig(
                sl_atr_multiplier=1.5,      # SL = entry ± 1.5*ATR
                tp_atr_multiplier=2.0,      # TP = entry ± 2.0*ATR
                sl_percent_fallback=1.0,    # Если ATR нет, используем 1% от цены
                tp_percent_fallback=2.0,    # Если ATR нет, используем 2% от цены
                use_exchange_sl_tp=True,    # Попытаться использовать биржевые SL/TP
                use_virtual_levels=True,    # Fallback на виртуальное отслеживание
                enable_trailing_stop=True,  # Включить trailing stop
            )
            self.sl_tp_manager = StopLossTakeProfitManager(self.order_manager, sl_tp_config)
            logger.info(f"SL/TP manager initialized with ATR-based levels")
        else:
            self.sl_tp_manager = None

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
            logger.info(f"Signal handler initialized with action config")
        else:
            self.signal_handler = None

        self.pipeline = FeaturePipeline()
        self.meta_layer = MetaLayer(strategies)

        # Risk
        self.position_sizer = PositionSizer()
        self.risk_limits = RiskLimits(self.db)
        self.circuit_breaker = CircuitBreaker()
        self.kill_switch = KillSwitch(self.db)
        
        # Advanced Risk Limits (D2 - для проверки leverage/notional/daily_loss/drawdown)
        if mode == "live":
            risk_config = RiskLimitsConfig(
                max_leverage=Decimal("10"),
                max_notional=Decimal("50000"),
                daily_loss_limit_percent=Decimal("5"),
                max_drawdown_percent=Decimal("10"),
            )
            self.advanced_risk_limits = AdvancedRiskLimits(self.db, risk_config)
            logger.info("Advanced risk limits initialized (leverage/notional/daily_loss/drawdown)")
        else:
            self.advanced_risk_limits = None

        # Kill Switch Manager (для аварийного закрытия)
        if mode == "live":
            from exchange.base_client import BybitRestClient
            rest_client = BybitRestClient(testnet=testnet)
            self.kill_switch_manager = KillSwitchManager(rest_client)
            logger.info("Kill switch manager initialized for emergency shutdown")
        else:
            self.kill_switch_manager = None

        # Execution
        if mode == "live":
            from exchange.base_client import BybitRestClient

            rest_client = BybitRestClient(testnet=testnet)
            self.order_manager = OrderManager(rest_client, self.db)
            self.position_manager = PositionManager(self.order_manager)
        else:
            # Paper mode: используем симуляцию
            self.order_manager = None
            self.position_manager = None

        logger.info("TradingBot initialized successfully")

    def run(self):
        """Главный цикл бота"""
        logger.info(f"Starting bot in {self.mode.upper()} mode...")

        # Проверка kill switch
        if self.kill_switch.check_status():
            logger.error("Kill switch is active! Cannot start. Reset with confirmation first.")
            return

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
                    data["df"], orderbook=data.get("orderbook")
                )

                features = data.get("orderflow_features", {})

                # 3. Проверяем circuit breaker
                if not self.circuit_breaker.is_trading_allowed():
                    logger.warning(
                        f"Trading halted by circuit breaker: {self.circuit_breaker.break_reason}"
                    )
                    time.sleep(60)
                    continue

                # 4. Получаем сигнал от стратегий
                signal = self.meta_layer.get_signal(df_with_features, features)

                if signal:
                    # Логируем сгенерированный сигнал
                    signal_logger.log_signal_generated(
                        strategy_name=signal.get('strategy', 'Unknown'),
                        symbol=self.symbol,
                        direction=signal.get('signal', 'unknown').upper(),
                        confidence=signal.get('confidence', 0),
                        price=signal.get('entry_price', 0),
                        reason=signal.get('reason', ''),
                    )
                    self._process_signal(signal)
                else:
                    # Логируем отладочную информацию - нет сигналов
                    signal_logger.log_debug_info(
                        category="market_analysis",
                        symbol=self.symbol,
                        last_close=float(df_with_features.iloc[-1]['close']),
                        no_signal_reason="No strategy triggered"
                    )

                # 5. Обновляем метрики
                self._update_metrics()

                # 6. Проверяем SL/TP уровни и виртуальные триггеры (если в live mode)
                if self.mode == "live" and self.sl_tp_manager and data.get("df") is not None:
                    current_price = Decimal(str(data["df"].iloc[-1]["close"]))
                    current_atr = data["df"].iloc[-1].get("atr")
                    
                    # Проверяем все активные позиции на SL/TP триггеры
                    for position_id, sl_tp_levels in self.sl_tp_manager.get_all_active_levels().items():
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
            try:
                kline_resp = retry_api_call(
                    self.market_client.get_kline,
                    self.symbol,
                    interval="60",
                    limit=500,
                    max_retries=2
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

            df = df.sort_values("timestamp").reset_index(drop=True)
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
                            max_retries=1
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
                                logger.debug(f"Loaded {len(tf_candles)} candles for {tf_name} timeframe")
                        else:
                            logger.debug(f"Failed to fetch {tf_name} data")
                    except Exception as e:
                        logger.debug(f"Error fetching {tf_name} data: {e}")
            else:
                logger.debug("MTF disabled or cache not available")

            # Orderbook с retry
            orderbook_resp = retry_api_call(
                self.market_client.get_orderbook,
                self.symbol,
                limit=50,
                max_retries=2
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
                max_retries=2
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
                max_retries=2
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
                max_retries=2
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
                self.market_client.get_funding_rate_history,
                self.symbol,
                limit=1,
                max_retries=2
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
                "df": df,
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
            strategy_name=signal.get('strategy', 'Unknown'),
            symbol=self.symbol,
            direction=signal.get('signal', 'unknown').upper(),
            confidence=signal.get('confidence', 0),
        )

        # В paper mode просто логируем
        if self.mode == "paper":
            logger.info(f"[PAPER] Would open {signal['signal']} @ {signal['entry_price']}")
            self.db.save_signal(
                strategy=signal.get("strategy", "Unknown"),
                symbol=self.symbol,
                signal_type=signal["signal"],
                price=signal["entry_price"],
                metadata=signal,
            )
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
                        if self.position_state_manager and self.position_state_manager.has_position() 
                        else None
                    )
                    
                    current_notional = Decimal("0")
                    current_leverage = Decimal("1")
                    if current_pos:
                        current_notional = Decimal(str(current_pos.qty)) * Decimal(str(signal.get("entry_price", 0)))
                        current_leverage = Decimal(str(current_pos.qty)) * Decimal(str(signal.get("entry_price", 0))) / Decimal(str(account_balance))
                    
                    # Предполагаемый размер новой позиции
                    new_position_notional = Decimal(str(signal.get("position_size", 0))) * Decimal(str(signal.get("entry_price", 0)))
                    
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
                    
                    logger.info(f"Risk evaluation: {risk_decision.value.upper()} - {risk_details['reason']}")
                    
                    if risk_decision == RiskDecision.DENY:
                        logger.warning(f"Trade blocked by risk limits: {risk_details['reason']}")
                        signal_logger.log_debug_info(
                            category="trade_blocked_risk",
                            symbol=self.symbol,
                            reason=risk_details['reason'],
                        )
                        return
                    
                    elif risk_decision == RiskDecision.STOP:
                        logger.critical(f"CRITICAL RISK VIOLATION - Triggering kill switch: {risk_details['reason']}")
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
                current_pos = self.position_state_manager.get_position() if self.position_state_manager.has_position() else None
                
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

                # 2. Расчитаем размер позиции
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

                if qty <= 0:
                    logger.warning("Position size too small, skipping trade")
                    return

                # 3. Нормализуем ордер согласно instrument rules (tickSize, qtyStep, минималы)
                logger.debug(f"Normalizing order: price={signal['entry_price']}, qty={qty}")
                normalized_price, normalized_qty, is_valid, norm_message = normalize_order(
                    self.instruments_manager,
                    self.symbol,
                    signal["entry_price"],
                    qty,
                )

                if not is_valid:
                    logger.warning(f"Order normalization failed: {norm_message}")
                    return

                # Логируем нормализованные значения для отладки
                if float(normalized_price) != signal["entry_price"] or float(normalized_qty) != qty:
                    logger.info(
                        f"Order normalized: "
                        f"price {signal['entry_price']} → {normalized_price}, "
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
                    logger.warning(f"Trade rejected by risk limits: {limits_check.get('violations')}")
                    return

                # 5. Выставляем ордер с нормализованными значениями
                side = "Buy" if signal["signal"] == "long" else "Sell"
                order_result = self.order_manager.create_order(
                    category="linear",
                    symbol=self.symbol,
                    side=side,
                    order_type="Market",
                    qty=float(normalized_qty),  # Используем нормализованное количество
                    order_link_id=f"bot_{int(time.time() * 1000)}",
                )

                if order_result.get("retCode") == 0:
                    order_id = order_result.get("result", {}).get("orderId")
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
                        f"Position registered in state manager: "
                        f"{side_long} {normalized_qty} @ {normalized_price}, orderId={order_id}"
                    )

                    # 7. Рассчитываем и выставляем SL/TP уровни на основе ATR
                    sl_tp_levels = None
                    if self.sl_tp_manager and data.get("df") is not None:
                        current_atr = data["df"].iloc[-1].get("atr")
                        
                        sl_tp_levels = self.sl_tp_manager.calculate_levels(
                            position_id=order_id,
                            symbol=self.symbol,
                            side=side_long,
                            entry_price=Decimal(str(normalized_price)),
                            entry_qty=Decimal(str(normalized_qty)),
                            current_atr=Decimal(str(current_atr)) if current_atr else None,
                        )

                        logger.info(
                            f"[LIVE] SL/TP levels calculated: "
                            f"SL={sl_tp_levels.sl_price}, TP={sl_tp_levels.tp_price} "
                            f"(ATR={current_atr})"
                        )

                        # Пытаемся выставить SL/TP на бирже (если поддерживается)
                        exchange_success, sl_order_id, tp_order_id = self.sl_tp_manager.place_exchange_sl_tp(
                            position_id=order_id,
                            category="linear",
                        )

                        if exchange_success and (sl_order_id or tp_order_id):
                            logger.info(
                                f"Exchange SL/TP orders placed: "
                                f"SL={sl_order_id}, TP={tp_order_id}"
                            )
                        else:
                            logger.info(
                                f"Using virtual SL/TP monitoring for {order_id}"
                            )

                    # 8. Регистрируем позицию в PositionManager для сопровождения (если используется)
                    if self.position_manager:
                        self.position_manager.register_position(
                            symbol=self.symbol,
                            side=side,
                            entry_price=float(normalized_price),
                            size=float(normalized_qty),
                            stop_loss=float(sl_tp_levels.sl_price) if sl_tp_levels else signal["stop_loss"],
                            take_profit=float(sl_tp_levels.tp_price) if sl_tp_levels else signal.get("take_profit"),
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
                    logger.error(f"Failed to place order: {order_result}")

            except Exception as e:
                logger.error(f"Error processing live signal: {e}", exc_info=True)

    def _update_metrics(self):
        """Обновить метрики и equity"""
        pass  # TODO: Реализовать сбор метрик

    def stop(self):
        """Остановить бота"""
        logger.info("Stopping bot...")
        self.is_running = False
