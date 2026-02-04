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
from logger import setup_logger

logger = setup_logger(__name__)


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
        logger.info(f"🚀 Starting bot in {self.mode.upper()} mode...")

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
                    self._process_signal(signal)

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
        """Получить рыночные данные"""
        try:
            import pandas as pd

            # Kline
            kline_resp = self.market_client.get_kline(self.symbol, interval="60", limit=500)
            if kline_resp.get("retCode") != 0:
                return None

            candles = kline_resp.get("result", {}).get("list", [])
            df = pd.DataFrame(
                candles,
                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],
            )

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            df = df.sort_values("timestamp").reset_index(drop=True)

            # Orderbook
            orderbook_resp = self.market_client.get_orderbook(self.symbol, limit=50)
            orderbook = None
            orderflow_features = {}

            if orderbook_resp.get("retCode") == 0:
                result = orderbook_resp.get("result", {})
                orderbook = {"bids": result.get("b", []), "asks": result.get("a", [])}
                orderflow_features = self.pipeline.calculate_orderflow_features(orderbook)

            self.circuit_breaker.update_data_timestamp()

            return {
                "df": df,
                "orderbook": orderbook,
                "orderflow_features": orderflow_features,
            }

        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return None

    def _process_signal(self, signal: Dict[str, Any]):
        """Обработать торговый сигнал"""
        logger.info(f"Processing signal: {signal['signal']} from {signal.get('strategy')}")

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
            # TODO: Добавить полную логику размещения ордеров
            logger.info("[LIVE] Opening position...")

    def _update_metrics(self):
        """Обновить метрики и equity"""
        pass  # TODO: Реализовать сбор метрик

    def stop(self):
        """Остановить бота"""
        logger.info("Stopping bot...")
        self.is_running = False
