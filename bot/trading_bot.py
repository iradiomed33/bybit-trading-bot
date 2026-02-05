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
from data.features import FeaturePipeline
from strategy.meta_layer import MetaLayer
from risk import PositionSizer, RiskLimits, CircuitBreaker, KillSwitch
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

        self.pipeline = FeaturePipeline()
        self.meta_layer = MetaLayer(strategies)

        # Risk
        self.position_sizer = PositionSizer()
        self.risk_limits = RiskLimits(self.db)
        self.circuit_breaker = CircuitBreaker()
        self.kill_switch = KillSwitch(self.db)

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

                # 6. Синхронизируем состояние позиции с биржей (если в live mode)
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
                # 0. Проверяем есть ли уже открытая позиция (предотвращаем дубликаты)
                if self.position_state_manager.has_position():
                    logger.warning(
                        f"Position already open for {self.symbol}. "
                        f"Skipping new trade signal to prevent duplicate positions."
                    )
                    return

                # 1. Получаем баланс аккаунта
                balance_result = self.account_client.get_wallet_balance(coin="USDT")
                account_balance = balance_result.get("balance", 0)
                
                if account_balance <= 0:
                    logger.error(f"Invalid account balance: {account_balance}")
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

                    # 7. Регистрируем позицию в PositionManager для сопровождения (если используется)
                    if self.position_manager:
                        self.position_manager.register_position(
                            symbol=self.symbol,
                            side=side,
                            entry_price=float(normalized_price),
                            size=float(normalized_qty),
                            stop_loss=signal["stop_loss"],
                            take_profit=signal.get("take_profit"),
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
