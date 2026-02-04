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
        print("Commands:")
        print("  health     - Check configuration and system health")
        print("  market     - Test market data endpoints")
        print("  stream     - Test WebSocket streams")
        print("  state      - Test state recovery (requires API keys)")
        print("  features   - Test feature pipeline")
        print("  risk       - Test risk engine")
        print("  execution  - Test execution engine (requires API keys)")
        print("  strategy   - Test strategies and meta-layer")
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
            f"ADX: {latest.get('ADX_14', 'N/A'):.2f}"
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
                logger.info(f"  ✓ Order cancelled")
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


if __name__ == "__main__":
    main()
