"""
Trading Bot: главный класс для paper и live режимов.

Объединяет:
- Data feeds (REST/WS)
- Feature pipeline
- Strategies + Meta-layer
- Risk engine
- Execution engine
"""

import time
from typing import Dict, Any, Optional
from storage.database import Database
from exchange.market_data import MarketDataClient
from exchange.account import AccountClient
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

            # Kline (основные данные с retry)
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
            logger.debug(f"Loaded {len(df)} candles")

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
                # Расчитаем размер позиции
                qty = self.position_sizer.calculate_size(
                    account_balance=self.account.get_balance(),
                    entry_price=signal["entry_price"],
                    stop_loss=signal["stop_loss"],
                    risk_percent=0.02,  # 2% риска на сделку
                )

                if qty <= 0:
                    logger.warning("Position size too small, skipping trade")
                    return

                # Проверяем риск-лимиты
                if not self.risk_limits.check_limits(
                    position_size=qty,
                    entry_price=signal["entry_price"],
                    daily_loss=0,  # TODO: получить из БД
                    consecutive_losses=0,  # TODO: получить из circuit breaker
                ):
                    logger.warning("Trade rejected by risk limits")
                    return

                # Выставляем ордер
                side = "Buy" if signal["signal"] == "long" else "Sell"
                order_result = self.order_manager.create_order(
                    category="linear",
                    symbol=self.symbol,
                    side=side,
                    order_type="Market",
                    qty=qty,
                    order_link_id=f"bot_{int(time.time() * 1000)}",
                )

                if order_result.get("retCode") == 0:
                    order_id = order_result.get("result", {}).get("orderId")
                    logger.info(f"✓ Order placed: {order_id}")

                    # Регистрируем позицию для сопровождения
                    self.position_manager.register_position(
                        symbol=self.symbol,
                        side=side,
                        entry_price=signal["entry_price"],
                        size=qty,
                        stop_loss=signal["stop_loss"],
                        take_profit=signal.get("take_profit"),
                    )

                    # Сохраняем сигнал в БД
                    self.db.save_signal(
                        strategy=signal.get("strategy", "Unknown"),
                        symbol=self.symbol,
                        signal_type=signal["signal"],
                        price=signal["entry_price"],
                        metadata=signal,
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
