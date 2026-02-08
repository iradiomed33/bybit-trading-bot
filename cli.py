"""

Command Line Interface для управления ботом.

Пока только health check команда.

"""


import time

import sys

from logger import setup_logger

from config import Config


logger = setup_logger()


def health_check():
    """Проверка конфигурации и работоспособности"""

    logger.info("=== Health Check Started ===")

    try:

        # Валидация конфига

        Config.validate()

        logger.info("✓ Configuration valid")

        logger.info(f"  - Environment: {Config.ENVIRONMENT}")

        logger.info(f"  - Mode: {Config.MODE}")

        logger.info(f"  - REST URL: {Config.get_rest_url()}")

        logger.info(f"  - WS URL: {Config.get_ws_url()}")

        logger.info(f"  - Log level: {Config.LOG_LEVEL}")

        # Проверка модулей

        modules = ["exchange", "data", "strategy", "risk", "execution", "portfolio", "storage"]

        for module in modules:

            try:

                __import__(module)

                logger.info(f"✓ Module '{module}' loaded")

            except ImportError as e:

                logger.warning(f"✗ Module '{module}' not fully implemented: {e}")

        logger.info("=== Health Check Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Health check failed: {e}")

        logger.info("=== Health Check Failed ===")

        return 1


def main():
    """Точка входа CLI"""

    if len(sys.argv) < 2:

        print("Usage: python cli.py <command>")

        print("\nTesting:")

        print("  health     - Check configuration and system health")

        print("  market     - Test market data endpoints")

        print("  stream     - Test WebSocket streams")

        print("  state      - Test state recovery")

        print("  features   - Test feature pipeline")

        print("  risk       - Test risk engine")

        print("  execution  - Test execution engine")

        print("  strategy   - Test strategies and meta-layer")

        print("\nTrading:")

        print("  backtest   - Run backtest on historical data")

        print("  paper      - Run paper trading (simulation)")

        print("  live       - Run live trading (REAL MONEY)")

        print("\nEmergency:")

        print("  kill       - Activate emergency kill switch (closes all positions)")

        print("\nManagement:")

        print("  config     - Manage bot configuration")

        print("  reset-kill-switch - Reset emergency stop flag after crash")

        sys.exit(1)

    command = sys.argv[1]

    if command == "health":

        sys.exit(health_check())

    elif command == "market":

        sys.exit(market_data_test())

    elif command == "stream":

        sys.exit(stream_test())

    elif command == "state":

        sys.exit(state_recovery_test())

    elif command == "features":

        sys.exit(features_test())

    elif command == "risk":

        sys.exit(risk_test())

    elif command == "execution":

        sys.exit(execution_test())

    elif command == "strategy":

        sys.exit(strategy_test())

    elif command == "backtest":

        sys.exit(backtest_command())

    elif command == "paper":

        sys.exit(paper_command())

    elif command == "live":

        sys.exit(live_command())

    elif command == "kill":

        sys.exit(kill_command())

    elif command == "reset-kill-switch":

        sys.exit(reset_kill_switch())

    elif command == "config":

        sys.exit(config_command())

    else:

        logger.error(f"Unknown command: {command}")

        sys.exit(1)


def market_data_test():
    """Тест market data эндпоинтов"""

    from exchange.market_data import MarketDataClient

    logger.info("=== Market Data Test Started ===")

    try:

        # Используем testnet из конфига

        testnet = Config.ENVIRONMENT == "testnet"

        client = MarketDataClient(testnet=testnet)

        # 1. Server time

        logger.info("1. Fetching server time...")

        time_resp = client.get_server_time()

        logger.info(f"   Server time: {time_resp.get('result', {}).get('timeNano', 'N/A')}")

        # 2. Instruments info

        logger.info("2. Fetching instruments info (BTCUSDT)...")

        instruments_resp = client.get_instruments_info(category="linear", symbol="BTCUSDT")

        if instruments_resp.get("retCode") == 0:

            instruments = instruments_resp.get("result", {}).get("list", [])

            if instruments:

                inst = instruments[0]

                logger.info(f"   ✓ Symbol: {inst.get('symbol')}")

                logger.info(f"   ✓ Tick size: {inst.get('priceFilter', {}).get('tickSize')}")

                logger.info(f"   ✓ Qty step: {inst.get('lotSizeFilter', {}).get('qtyStep')}")

                logger.info(f"   ✓ Min qty: {inst.get('lotSizeFilter', {}).get('minOrderQty')}")

            else:

                logger.warning("   No instruments found")

        # 3. Kline

        logger.info("3. Fetching kline (BTCUSDT, 1h, last 5 candles)...")

        kline_resp = client.get_kline(symbol="BTCUSDT", interval="60", limit=5)

        if kline_resp.get("retCode") == 0:

            candles = kline_resp.get("result", {}).get("list", [])

            logger.info(f"   ✓ Received {len(candles)} candles")

            if candles:

                # Первая свеча [timestamp, open, high, low, close, volume, turnover]

                first = candles[0]

                logger.info(

                    f"   Latest: O={first[1]}, H={first[2]}, "

                    f"L={first[3]}, C={first[4]}, V={first[5]}"

                )

        # 4. Orderbook

        logger.info("4. Fetching orderbook (BTCUSDT, depth=50)...")

        orderbook_resp = client.get_orderbook(symbol="BTCUSDT", limit=5)

        if orderbook_resp.get("retCode") == 0:

            result = orderbook_resp.get("result", {})

            bids = result.get("b", [])

            asks = result.get("a", [])

            logger.info(f"   ✓ Bids: {len(bids)}, Asks: {len(asks)}")

            if bids and asks:

                logger.info(f"   Best bid: {bids[0][0]} (qty: {bids[0][1]})")

                logger.info(f"   Best ask: {asks[0][0]} (qty: {asks[0][1]})")

                spread = float(asks[0][0]) - float(bids[0][0])

                logger.info(f"   Spread: {spread:.2f}")

        logger.info("=== Market Data Test Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Market data test failed: {e}", exc_info=True)

        logger.info("=== Market Data Test Failed ===")

        return 1


def stream_test():
    """Тест WebSocket streams (kline + orderbook)"""

    import signal

    import sys

    logger.info("=== WebSocket Stream Test Started ===")

    logger.info("Press Ctrl+C to stop")

    testnet = Config.ENVIRONMENT == "testnet"

    symbol = "BTCUSDT"

    kline_count = [0]  # Используем список для изменения в closure

    orderbook_count = [0]

    def on_kline(kline_data):
        """Callback для kline"""

        kline_count[0] += 1

        confirm = kline_data.get("confirm", False)

        close_price = kline_data.get("close", "N/A")

        volume = kline_data.get("volume", "N/A")

        logger.info(

            f"[Kline #{kline_count[0]}] Close: {close_price}, "

            f"Volume: {volume}, Confirmed: {confirm}"

        )

    def on_orderbook(orderbook):
        """Callback для orderbook"""

        orderbook_count[0] += 1

        bids = orderbook["bids"]

        asks = orderbook["asks"]

        if bids and asks:

            best_bid = bids[0][0]

            best_ask = asks[0][0]

            spread = float(best_ask) - float(best_bid)

            logger.info(

                f"[Orderbook #{orderbook_count[0]}] Best bid: {best_bid}, "

                f"Best ask: {best_ask}, Spread: {spread:.2f}"

            )

    try:

        from exchange.streams import KlineStream, OrderbookStream

        # Kline stream (1 минута)

        logger.info(f"Starting Kline stream: {symbol} 1m")

        kline_stream = KlineStream(symbol, "1", on_kline, testnet)

        kline_stream.start()

        # Orderbook stream (глубина 50)

        logger.info(f"Starting Orderbook stream: {symbol} depth=50")

        orderbook_stream = OrderbookStream(symbol, 50, on_orderbook, testnet)

        orderbook_stream.start()

        # Graceful shutdown при Ctrl+C

        def signal_handler(sig, frame):

            logger.info("\n=== Stopping streams... ===")

            kline_stream.stop()

            orderbook_stream.stop()

            logger.info(f"Total klines received: {kline_count[0]}")

            logger.info(f"Total orderbook updates: {orderbook_count[0]}")

            logger.info("=== WebSocket Stream Test Stopped ===")

            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Держим программу активной

        logger.info("Streams running... Press Ctrl+C to stop")

        while True:

            time.sleep(1)

    except Exception as e:

        logger.error(f"✗ Stream test failed: {e}", exc_info=True)

        return 1


def state_recovery_test():
    """Тест восстановления состояния (требует API ключи)"""

    logger.info("=== State Recovery Test Started ===")

    # Проверяем наличие API ключей

    if not Config.BYBIT_API_KEY or not Config.BYBIT_API_SECRET:

        logger.error("API keys required for state recovery")

        logger.info("Please set BYBIT_API_KEY and BYBIT_API_SECRET in .env file")

        return 1

    try:

        from storage.database import Database

        from exchange.account import AccountClient

        from storage.state_recovery import StateRecovery

        # Инициализация

        testnet = Config.ENVIRONMENT == "testnet"

        db = Database()

        account_client = AccountClient(testnet=testnet)

        recovery = StateRecovery(db, account_client)

        # Восстановление состояния

        result = recovery.recover_state(category="linear")

        if result["success"]:

            logger.info("✓ State recovery successful")

            logger.info(f"  - Positions synced: {result['positions_synced']}")

            logger.info(f"  - Orders synced: {result['orders_synced']}")

            if result["discrepancies"]:

                logger.warning("Discrepancies found:")

                for disc in result["discrepancies"]:

                    logger.warning(f"  - {disc}")

            else:

                logger.info("  - No discrepancies found")

            logger.info("=== State Recovery Test Passed ===")

            return 0

        else:

            logger.error("✗ State recovery failed")

            return 1

    except Exception as e:

        logger.error(f"✗ State recovery test failed: {e}", exc_info=True)

        return 1


def features_test():
    """Тест feature pipeline"""

    logger.info("=== Features Test Started ===")

    try:

        from exchange.market_data import MarketDataClient

        from data.features import FeaturePipeline

        import pandas as pd

        testnet = Config.ENVIRONMENT == "testnet"

        market_client = MarketDataClient(testnet=testnet)

        pipeline = FeaturePipeline()

        # Получаем исторические данные

        symbol = "BTCUSDT"

        logger.info(f"Fetching kline data for {symbol}...")

        kline_resp = market_client.get_kline(symbol, interval="60", limit=500)

        if kline_resp.get("retCode") != 0:

            logger.error("Failed to fetch kline data")

            return 1

        # Преобразуем в DataFrame

        candles = kline_resp.get("result", {}).get("list", [])

        df = pd.DataFrame(

            candles,

            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],

        )

        # Конвертируем типы

        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")

        for col in ["open", "high", "low", "close", "volume"]:

            df[col] = df[col].astype(float)

        # Сортируем по времени (Bybit возвращает в обратном порядке)

        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Data loaded: {len(df)} candles")

        # Получаем стакан

        logger.info("Fetching orderbook...")

        orderbook_resp = market_client.get_orderbook(symbol, limit=50)

        orderbook = None

        if orderbook_resp.get("retCode") == 0:

            result = orderbook_resp.get("result", {})

            orderbook = {"bids": result.get("b", []), "asks": result.get("a", [])}

        # Строим фичи

        logger.info("Building features...")

        df_with_features = pipeline.build_features(df, orderbook=orderbook)

        # Показываем последние значения

        logger.info("=== Latest Features ===")

        latest = df_with_features.iloc[-1]

        # Trend

        logger.info(

            f"[Trend] EMA20: {latest.get('ema_20', 'N/A'):.2f}, "

            f"ADX: {latest.get('adx', latest.get('ADX_14', 'N/A')):.2f}"

        )

        # Volatility

        logger.info(

            f"[Volatility] ATR%: {latest.get('atr_percent', 'N/A'):.2f}, "

            f"Vol Regime: {latest.get('vol_regime', 'N/A')}"

        )

        # Volume

        logger.info(

            f"[Volume] Z-score: {latest.get('volume_zscore', 'N/A'):.2f}, "

            f"VWAP dist: {latest.get('vwap_distance', 'N/A'):.2f}%"

        )

        # Order Flow

        if orderbook:

            logger.info(

                f"[OrderFlow] Spread: {latest.get('spread', 'N/A'):.2f}, "

                f"Imbalance: {latest.get('depth_imbalance', 'N/A'):.2f}"

            )

        # Data Quality

        logger.info(f"[Quality] Has anomaly: {latest.get('has_anomaly', 'N/A')}")

        logger.info(f"Total features: {len(df_with_features.columns)}")

        logger.info("=== Features Test Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Features test failed: {e}", exc_info=True)

        return 1


def risk_test():
    """Тест risk engine"""

    logger.info("=== Risk Engine Test Started ===")

    try:

        from risk import PositionSizer, RiskLimits, CircuitBreaker, KillSwitch

        from storage.database import Database

        # 1. Position Sizer

        logger.info("\n[1] Testing Position Sizer...")

        sizer = PositionSizer(risk_per_trade_percent=2.0, max_leverage=10.0)

        result = sizer.calculate_position_size(

            account_balance=10000.0,  # $10,000

            entry_price=100000.0,  # BTC at $100k

            stop_loss_price=98000.0,  # 2% stop

            side="Buy",

        )

        if result["success"]:

            logger.info(f"  ✓ Position size: {result['position_size']} BTC")

            logger.info(f"  ✓ Position value: ${result['position_value']}")

            logger.info(f"  ✓ Required leverage: {result['required_leverage']}x")

            logger.info(f"  ✓ Risk amount: ${result['risk_amount']}")

        else:

            logger.error(f"  ✗ Position sizing failed: {result.get('error')}")

        # 2. Risk Limits

        logger.info("\n[2] Testing Risk Limits...")

        db = Database()

        limits = RiskLimits(

            db,

            max_daily_loss_percent=5.0,

            max_trades_per_day=20,

            max_concurrent_positions=3,

        )

        # Проверяем лимиты для новой сделки

        proposed_trade = {"symbol": "BTCUSDT", "size": 0.1, "value": 10000.0}

        check_result = limits.check_limits(account_balance=10000.0, proposed_trade=proposed_trade)

        if check_result["allowed"]:

            logger.info("  ✓ Trade allowed by risk limits")

        else:

            logger.warning(f"  ✗ Trade blocked: {check_result['violations']}")

        # Симулируем превышение лимита

        limits.trades_today = 25  # Больше макс.

        check_result2 = limits.check_limits(account_balance=10000.0, proposed_trade=proposed_trade)

        if not check_result2["allowed"]:

            logger.info(f"  ✓ Correctly blocked trade: {check_result2['violations'][0]}")

        # 3. Circuit Breaker

        logger.info("\n[3] Testing Circuit Breaker...")

        breaker = CircuitBreaker(max_consecutive_losses=3, max_spread_percent=1.0)

        # Симулируем серию убытков

        for i in range(1, 4):

            breaker.check_consecutive_losses("loss")

            if breaker.is_circuit_broken:

                logger.info(f"  ✓ Circuit breaker triggered after {i} losses")

                break

        # 4. Kill Switch

        logger.info("\n[4] Testing Kill Switch...")

        kill_switch = KillSwitch(db)

        # Проверяем статус

        if not kill_switch.check_status():

            logger.info("  ✓ Kill switch not active")

        # Активируем

        kill_switch.activate("Test activation")

        if kill_switch.is_activated:

            logger.info("  ✓ Kill switch activated successfully")

        # Сбрасываем

        if kill_switch.reset("RESET"):

            logger.info("  ✓ Kill switch reset successfully")

        logger.info("\n=== Risk Engine Test Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Risk engine test failed: {e}", exc_info=True)

        return 1


def execution_test():
    """Тест execution engine (требует API ключи)"""

    logger.info("=== Execution Engine Test Started ===")

    if not Config.BYBIT_API_KEY or not Config.BYBIT_API_SECRET:

        logger.error("API keys required for execution test")

        return 1

    try:

        from exchange.base_client import BybitRestClient

        from storage.database import Database

        from execution import OrderManager, PositionManager

        testnet = Config.ENVIRONMENT == "testnet"

        client = BybitRestClient(testnet=testnet)

        db = Database()

        # Order Manager

        logger.info("\n[1] Testing Order Manager...")

        order_mgr = OrderManager(client, db)

        # ВНИМАНИЕ: Это создаст реальный ордер на testnet!

        # Раскомментируйте только если готовы

        """

        result = order_mgr.create_order(

            category="linear",

            symbol="BTCUSDT",

            side="Buy",

            order_type="Limit",

            qty=0.001,

            price=50000.0,  # Заведомо низкая цена, не исполнится

            time_in_force="PostOnly"

        )


        if result["success"]:

            logger.info(f"  ✓ Order created: {result['order_id']}")


            # Отменяем сразу

            time.sleep(1)

            cancel_result = order_mgr.cancel_order(

                category="linear",

                symbol="BTCUSDT",

                order_id=result["order_id"]

            )


            if cancel_result["success"]:

                logger.info("  ✓ Order cancelled")

        """

        logger.info("  ✓ Order Manager initialized (actual order test skipped)")

        # Position Manager

        logger.info("\n[2] Testing Position Manager...")

        pos_mgr = PositionManager(order_mgr)

        # Регистрируем тестовую позицию

        pos_mgr.register_position(

            symbol="BTCUSDT",

            side="Buy",

            entry_price=100000.0,

            size=0.1,

            stop_loss=98000.0,  # 2% риск

            take_profit=104000.0,  # 4% профит (R:R = 1:2)

            breakeven_trigger=1.5,  # Б/у при 1.5R

        )

        # Симулируем движение цены

        logger.info("\n[3] Simulating price movement...")

        # Цена 101000 - небольшой профит

        pos_mgr.update_position("BTCUSDT", 101000.0, 0.1)

        status = pos_mgr.get_position_status("BTCUSDT")

        logger.info(

            f"  Price 101000: BE moved={status['breakeven_moved']}, SL={status['stop_loss']}"

        )

        # Цена 103000 - достигнут BE trigger (1.5R)

        pos_mgr.update_position("BTCUSDT", 103000.0, 0.1)

        status = pos_mgr.get_position_status("BTCUSDT")

        logger.info(

            f"  Price 103000: BE moved={status['breakeven_moved']}, SL={status['stop_loss']}"

        )

        # Цена 105000 - трейлинг

        pos_mgr.update_position("BTCUSDT", 105000.0, 0.1)

        status = pos_mgr.get_position_status("BTCUSDT")

        logger.info(f"  Price 105000: Trailing SL={status['stop_loss']}")

        logger.info("\n=== Execution Engine Test Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Execution test failed: {e}", exc_info=True)

        return 1


def strategy_test():
    """Тест стратегий и meta-layer"""

    logger.info("=== Strategy Test Started ===")

    try:

        from exchange.market_data import MarketDataClient

        from data.features import FeaturePipeline

        from strategy import (

            TrendPullbackStrategy,

            BreakoutStrategy,

            MeanReversionStrategy,

            MetaLayer,

        )

        import pandas as pd

        testnet = Config.ENVIRONMENT == "testnet"

        market_client = MarketDataClient(testnet=testnet)

        pipeline = FeaturePipeline()

        # Получаем данные

        symbol = "BTCUSDT"

        logger.info(f"Fetching data for {symbol}...")

        kline_resp = market_client.get_kline(symbol, interval="60", limit=500)

        orderbook_resp = market_client.get_orderbook(symbol, limit=50)

        # Преобразуем в DataFrame

        candles = kline_resp.get("result", {}).get("list", [])

        df = pd.DataFrame(

            candles,

            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],

        )

        for col in ["open", "high", "low", "close", "volume"]:

            df[col] = df[col].astype(float)

        df = df.sort_values("timestamp").reset_index(drop=True)

        # Orderbook

        orderbook = None

        if orderbook_resp.get("retCode") == 0:

            result = orderbook_resp.get("result", {})

            orderbook = {"bids": result.get("b", []), "asks": result.get("a", [])}

        # Строим фичи

        logger.info("Building features...")

        df_with_features = pipeline.build_features(df, orderbook=orderbook)

        # Дополнительные фичи из orderbook

        features = {}

        if orderbook:

            features = pipeline.calculate_orderflow_features(orderbook)

        # Инициализируем стратегии

        logger.info("\n[1] Initializing strategies...")

        strategies = [

            TrendPullbackStrategy(),

            BreakoutStrategy(),

            MeanReversionStrategy(),

        ]

        # Meta-layer

        logger.info("\n[2] Creating meta-layer...")

        meta = MetaLayer(strategies)

        # Получаем сигнал

        logger.info("\n[3] Generating signal...")

        signal = meta.get_signal(df_with_features, features, error_count=0)

        if signal:

            logger.info("\n✓ SIGNAL GENERATED:")

            logger.info(f"  Direction: {signal['signal'].upper()}")

            logger.info(f"  Strategy: {signal.get('strategy', 'Unknown')}")

            logger.info(f"  Confidence: {signal['confidence']:.2f}")

            logger.info(f"  Entry: {signal['entry_price']:.2f}")

            logger.info(f"  Stop Loss: {signal['stop_loss']:.2f}")

            logger.info(f"  Take Profit: {signal.get('take_profit', 'N/A')}")

            logger.info(f"  Reason: {signal['reason']}")

            logger.info(f"  Regime: {signal.get('regime', 'Unknown')}")

        else:

            logger.info("\n✓ No signal (conditions not met or blocked)")

        logger.info("\n=== Strategy Test Passed ===")

        return 0

    except Exception as e:

        logger.error(f"✗ Strategy test failed: {e}", exc_info=True)

        return 1


def backtest_command():
    """Запуск backtest"""

    logger.info("=== Backtest Started ===")

    try:

        from exchange.market_data import MarketDataClient

        from data.features import FeaturePipeline

        from strategy import TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy

        from strategy.meta_layer import MetaLayer

        from backtest import BacktestEngine

        from storage.database import Database

        import pandas as pd

        # Получаем данные

        testnet = Config.ENVIRONMENT == "testnet"

        market_client = MarketDataClient(testnet=testnet)

        pipeline = FeaturePipeline()

        symbol = "BTCUSDT"

        logger.info(f"Fetching historical data for {symbol}...")

        kline_resp = market_client.get_kline(symbol, interval="60", limit=1000)  # Больше данных

        candles = kline_resp.get("result", {}).get("list", [])

        df = pd.DataFrame(

            candles,

            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],

        )

        for col in ["timestamp", "open", "high", "low", "close", "volume"]:

            df[col] = df[col].astype(float)

        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Data loaded: {len(df)} candles")

        # Строим фичи

        logger.info("Building features...")

        df_with_features = pipeline.build_features(df)

        # Стратегии

        strategies = [

            TrendPullbackStrategy(),

            BreakoutStrategy(),

            MeanReversionStrategy(),

        ]

        meta = MetaLayer(strategies)

        # Backtest engine

        db = Database()

        engine = BacktestEngine(db, initial_balance=10000.0)

        logger.info("Running backtest...")

        # Прогоняем через все свечи

        start_idx = 200  # Пропускаем первые 200 для прогрева индикаторов

        total_candles = len(df_with_features) - start_idx

        for i in range(start_idx, len(df_with_features)):

            current_df = df_with_features.iloc[: i + 1]

            current_price = current_df.iloc[-1]["close"]

            timestamp = current_df.iloc[-1]["timestamp"]

            # Проверяем выход

            engine.check_exit(timestamp, current_price)

            # Получаем сигнал

            if not engine.current_position:

                signal = meta.get_signal(current_df, {}, error_count=0)

                if signal:

                    engine.open_position(signal, timestamp, current_price)

            # Записываем equity

            engine.record_equity(timestamp, current_price)

            # Прогресс каждые 50 свечей

            if (i - start_idx + 1) % 50 == 0:

                progress = ((i - start_idx + 1) / total_candles) * 100

                print(

                    f"Progress: {progress:.1f}% ({i - start_idx + 1}/{total_candles})",

                    end="\r",

                )

        print()  # Новая строка после прогресса

        # Закрываем открытую позицию если есть

        if engine.current_position:

            engine.close_position(

                df_with_features.iloc[-1]["timestamp"],

                df_with_features.iloc[-1]["close"],

                "end_of_data",

            )

        # Метрики

        logger.info("\n=== Backtest Results ===")

        metrics = engine.calculate_metrics()

        if "error" in metrics:

            logger.warning(f"No trades executed: {metrics['error']}")

        else:

            for key, value in metrics.items():

                if isinstance(value, float):

                    logger.info(f"  {key}: {value:.2f}")

                else:

                    logger.info(f"  {key}: {value}")

        logger.info("\n=== Backtest Completed ===")

        return 0

    except Exception as e:

        logger.error(f"Backtest failed: {e}", exc_info=True)

        return 1


def paper_command():
    """Запуск paper trading"""

    logger.info("=== Paper Trading Mode ===")

    try:

        from strategy import TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy

        from bot import TradingBot

        strategies = [

            TrendPullbackStrategy(),

            BreakoutStrategy(),

            MeanReversionStrategy(),

        ]

        testnet = Config.ENVIRONMENT == "testnet"

        bot = TradingBot(mode="paper", strategies=strategies, testnet=testnet)

        bot.run()

        return 0

    except Exception as e:

        logger.error(f"Paper trading failed: {e}", exc_info=True)

        return 1


def live_command():
    """Запуск live trading"""

    logger.warning("=== LIVE TRADING MODE ===")

    logger.warning("⚠️  This will trade with REAL money!")

    confirmation = input("Type 'YES' to confirm: ")

    if confirmation != "YES":

        logger.info("Live trading cancelled")

        return 0

    try:

        from strategy import TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy

        from bot import TradingBot

        strategies = [

            TrendPullbackStrategy(),

            BreakoutStrategy(),

            MeanReversionStrategy(),

        ]

        testnet = Config.ENVIRONMENT == "testnet"

        bot = TradingBot(mode="live", strategies=strategies, testnet=testnet)

        bot.run()

        return 0

    except Exception as e:

        logger.error(f"Live trading failed: {e}", exc_info=True)

        return 1


def reset_kill_switch():
    """Сброс kill switch для перезапуска после аварийного завершения"""

    logger.warning("=== KILL SWITCH RESET ===")

    logger.warning("⚠️  Это сбросит флаг аварийного завершения.")

    logger.warning("Используй ТОЛЬКО если бот был аварийно остановлен.")

    confirmation = input("Type 'RESET' to confirm: ").strip()

    if confirmation != "RESET":

        logger.warning("Reset cancelled")

        return 1

    try:

        from storage.database import Database
        from risk.kill_switch import KillSwitch

        db = Database()

        # 1. Reset old KillSwitch (errors table) - use the proper reset method
        logger.info("Resetting KillSwitch (errors table)...")
        kill_switch = KillSwitch(db)
        success_old = kill_switch.reset("RESET")
        
        if success_old:
            logger.info("✓ KillSwitch reset successfully")
        else:
            logger.warning("✗ KillSwitch reset failed")

        # 2. Reset trading_disabled flag (config table)
        logger.info("Clearing trading_disabled flag...")
        try:
            db.save_config("trading_disabled", False)
            logger.info("✓ trading_disabled flag cleared")
            success_manager = True
        except Exception as e:
            logger.error(f"✗ Failed to clear trading_disabled flag: {e}")
            success_manager = False

        db.close()

        if success_old and success_manager:
            logger.info("✅ Kill switch has been reset completely!")
            logger.info("You can now start the bot with: python cli.py live")
            return 0
        else:
            logger.warning("⚠️  Kill switch reset completed with errors. Check logs above.")
            return 1

    except Exception as e:

        logger.error(f"Failed to reset kill switch: {e}", exc_info=True)

        return 1


def kill_command():
    """Активация kill switch - аварийное закрытие всех позиций и отмена ордеров"""

    logger.error("=" * 80)

    logger.error("EMERGENCY KILL SWITCH ACTIVATION")

    logger.error("=" * 80)

    logger.error("⚠️  This will IMMEDIATELY close ALL open positions and cancel ALL orders!")

    logger.error("⚠️  This operation CANNOT be undone!")

    logger.error("=" * 80)

    confirmation = input("\nType 'KILL' to activate emergency shutdown: ").strip()

    if confirmation != "KILL":

        logger.info("Kill switch activation cancelled")

        return 0

    try:

        from exchange.base_client import BybitRestClient

        from execution.kill_switch import KillSwitchManager

        from config import Config

        testnet = Config.ENVIRONMENT == "testnet"

        client = BybitRestClient(testnet=testnet)

        kill_switch = KillSwitchManager(client)

        # Activate kill switch

        logger.error("Activating emergency kill switch...")

        result = kill_switch.activate(

            reason="Manual emergency activation via CLI", cancel_orders=True, close_positions=True

        )

        # Report results

        logger.error("=" * 80)

        logger.error("KILL SWITCH RESULTS")

        logger.error("=" * 80)

        logger.error(f"Status: {'SUCCESS' if result['success'] else 'FAILED'}")

        logger.error(f"Timestamp: {result['timestamp']}")

        logger.error(f"Orders Cancelled: {result['orders_cancelled']}")

        logger.error(f"Positions Closed: {result['positions_closed']}")

        if result["errors"]:

            logger.error(f"\nErrors ({len(result['errors'])}):")

            for error in result["errors"]:

                logger.error(f"  - {error}")

        # Get final status

        status = kill_switch.get_status()

        logger.error("\n" + "=" * 80)

        logger.error("FINAL STATUS")

        logger.error("=" * 80)

        logger.error(f"Trading Halted: {status['is_halted']}")

        logger.error(f"Status: {status['status'].upper()}")

        logger.error(f"Total Orders Cancelled: {status['orders_cancelled']}")

        logger.error(f"Total Positions Closed: {status['positions_closed']}")

        logger.error("=" * 80)

        if result["success"]:

            logger.error("\n✅ EMERGENCY SHUTDOWN COMPLETE")

            logger.error("All positions are closed and no further trading can occur.")

            logger.error("To recover, use: python cli.py reset-kill-switch")

            return 0

        else:

            logger.error("\n❌ EMERGENCY SHUTDOWN ENCOUNTERED ERRORS")

            logger.error("Please verify all positions are closed manually.")

            return 1

    except Exception as e:

        logger.error(f"❌ Kill switch activation failed: {e}", exc_info=True)

        return 1


def config_command():
    """Управление конфигурацией бота"""

    from config import get_config

    import json

    if len(sys.argv) < 3:

        print("Usage: python cli.py config <action> [args]")

        print("\nActions:")

        print("  show              - Show current configuration")

        print("  get <key>         - Get config value (e.g., trading.symbol)")

        print("  set <key> <value> - Set config value (e.g., trading.symbol ETHUSDT)")

        print("  section <name>    - Show config section (e.g., risk_management)")

        print("  save              - Save current config to file")

        print("  reset             - Reset to default configuration")

        print("  validate          - Validate configuration")

        return 1

    action = sys.argv[2]

    config = get_config()

    try:

        if action == "show":

            logger.info("=== Current Configuration ===")

            print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))

            return 0

        elif action == "get":

            if len(sys.argv) < 4:

                logger.error("Usage: python cli.py config get <key>")

                return 1

            key = sys.argv[3]

            value = config.get(key)

            logger.info(f"{key} = {value}")

            return 0

        elif action == "set":

            if len(sys.argv) < 5:

                logger.error("Usage: python cli.py config set <key> <value>")

                return 1

            key = sys.argv[3]

            value = sys.argv[4]

            # Попытаемся распарсить как число

            try:

                if value.lower() in ("true", "false"):

                    value = value.lower() == "true"

                elif "." in value:

                    value = float(value)

                else:

                    value = int(value)

            except (ValueError, AttributeError):

                pass  # Оставляем как строку

            config.set(key, value)

            config.save()

            logger.info(f"✅ Config updated: {key} = {value}")

            return 0

        elif action == "section":

            if len(sys.argv) < 4:

                logger.error("Usage: python cli.py config section <name>")

                return 1

            section = sys.argv[3]

            data = config.get_section(section)

            logger.info(f"=== Section: {section} ===")

            print(json.dumps(data, indent=2, ensure_ascii=False))

            return 0

        elif action == "save":

            if config.save():

                logger.info("✅ Configuration saved")

                return 0

            else:

                logger.error("Failed to save configuration")

                return 1

        elif action == "reset":

            confirmation = input("Type 'RESET' to confirm reset to defaults: ").strip()

            if confirmation == "RESET":

                if config.reset_to_defaults():

                    logger.info("✅ Configuration reset to defaults")

                    return 0

            logger.warning("Reset cancelled")

            return 1

        elif action == "validate":

            is_valid, errors = config.validate()

            if is_valid:

                logger.info("✅ Configuration is valid")

                return 0

            else:

                logger.error("Configuration has errors:")

                for error in errors:

                    logger.error(f"  - {error}")

                return 1

        else:

            logger.error(f"Unknown action: {action}")

            return 1

    except Exception as e:

        logger.error(f"Config command failed: {e}", exc_info=True)

        return 1


if __name__ == "__main__":

    main()
