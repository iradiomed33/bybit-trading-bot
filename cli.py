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
        print("  health   - Check configuration and system health")
        print("  market   - Test market data endpoints")
        print("  stream   - Test WebSocket streams")
        print("  state    - Test state recovery (requires API keys)")
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


if __name__ == "__main__":
    main()
