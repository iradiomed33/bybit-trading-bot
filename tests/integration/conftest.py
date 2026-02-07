"""
Fixtures для интеграционных тестов на Bybit testnet.

Эти fixtures используются всеми integration тестами для:
- Загрузки testnet credentials из env
- Инициализации компонентов бота
- Cleanup после тестов
"""

import os
import time
import pytest
from decimal import Decimal
from dotenv import load_dotenv

# Загрузка .env файла
load_dotenv()

# Skip условие для всех тестов если нет credentials
skip_without_testnet = pytest.mark.skipif(
    not os.getenv("BYBIT_TESTNET_API_KEY") or not os.getenv("BYBIT_TESTNET_ENABLED"),
    reason="Testnet credentials not configured. Set BYBIT_TESTNET_API_KEY, BYBIT_TESTNET_API_SECRET, BYBIT_TESTNET_ENABLED in .env file"
)


@pytest.fixture(scope="session")
def testnet_credentials():
    """Testnet API credentials из environment variables"""
    api_key = os.getenv("BYBIT_TESTNET_API_KEY")
    api_secret = os.getenv("BYBIT_TESTNET_API_SECRET")
    
    if not api_key or not api_secret:
        pytest.skip("Testnet credentials not configured")
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "testnet": True,
    }


@pytest.fixture(scope="session")
def testnet_config(testnet_credentials):
    """Конфигурация для testnet"""
    return {
        "api_key": testnet_credentials["api_key"],
        "api_secret": testnet_credentials["api_secret"],
        "testnet": True,
        "symbol": "BTCUSDT",  # Основной символ для тестов
        "category": "linear",
    }


@pytest.fixture(scope="function")
def rest_client(testnet_config):
    """Инициализированный BybitRestClient для testnet"""
    from exchange.bybit_rest_client import BybitRestClient
    
    client = BybitRestClient(
        api_key=testnet_config["api_key"],
        api_secret=testnet_config["api_secret"],
        testnet=True,
    )
    
    return client


@pytest.fixture(scope="function")
def account_client(rest_client):
    """AccountClient для testnet"""
    from exchange.account_client import AccountClient
    
    client = AccountClient(rest_client)
    return client


@pytest.fixture(scope="function")
def database():
    """Database для тестов (in-memory SQLite)"""
    import tempfile
    from storage.database import Database
    
    # Используем временный файл
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db = Database(db_file.name)
    
    yield db
    
    # Cleanup
    db.conn.close()
    os.unlink(db_file.name)


@pytest.fixture(scope="function")
def order_manager(rest_client, database):
    """OrderManager для testnet"""
    from execution.order_manager import OrderManager
    
    manager = OrderManager(
        rest_client=rest_client,
        db=database,
        category="linear",
    )
    
    return manager


@pytest.fixture(scope="function")
def position_manager(database, testnet_config):
    """PositionManager для тестов"""
    from execution.position_manager import PositionManager
    
    manager = PositionManager(db=database)
    return manager


@pytest.fixture(scope="function")
def kill_switch(rest_client, order_manager, database, testnet_config):
    """KillSwitchManager для тестов"""
    from execution.kill_switch import KillSwitchManager
    
    manager = KillSwitchManager(
        client=rest_client,
        order_manager=order_manager,
        db=database,
        allowed_symbols=[testnet_config["symbol"]],
    )
    
    return manager


@pytest.fixture(scope="function")
def cleanup_positions(rest_client, testnet_config):
    """Helper для закрытия всех позиций после теста"""
    
    def _cleanup():
        """Закрыть все открытые позиции"""
        try:
            # Получить все позиции
            response = rest_client.post(
                "/v5/position/list",
                params={
                    "category": testnet_config["category"],
                    "settleCoin": "USDT",
                }
            )
            
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                
                for pos in positions:
                    size = float(pos.get("size", 0))
                    if size > 0:
                        # Закрыть позицию Market ордером
                        side = "Sell" if pos["side"] == "Buy" else "Buy"
                        rest_client.post(
                            "/v5/order/create",
                            params={
                                "category": testnet_config["category"],
                                "symbol": pos["symbol"],
                                "side": side,
                                "orderType": "Market",
                                "qty": str(size),
                                "timeInForce": "IOC",
                            }
                        )
                        time.sleep(0.5)
        except Exception as e:
            print(f"Cleanup positions error: {e}")
    
    yield _cleanup
    
    # Cleanup после теста
    _cleanup()


@pytest.fixture(scope="function")
def cleanup_orders(rest_client, testnet_config):
    """Helper для отмены всех ордеров после теста"""
    
    def _cleanup():
        """Отменить все открытые ордера"""
        try:
            rest_client.post(
                "/v5/order/cancel-all",
                params={
                    "category": testnet_config["category"],
                    "symbol": testnet_config["symbol"],
                }
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"Cleanup orders error: {e}")
    
    yield _cleanup
    
    # Cleanup после теста
    _cleanup()


@pytest.fixture(scope="function")
def wait_for_fill():
    """Helper для ожидания исполнения ордера"""
    
    def _wait(rest_client, order_id, max_wait=10):
        """
        Ждать пока ордер не будет исполнен
        
        Args:
            rest_client: BybitRestClient
            order_id: ID ордера
            max_wait: Максимальное время ожидания в секундах
            
        Returns:
            bool: True если ордер исполнен
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = rest_client.post(
                    "/v5/order/realtime",
                    params={
                        "category": "linear",
                        "orderId": order_id,
                    }
                )
                
                if response.get("retCode") == 0:
                    orders = response.get("result", {}).get("list", [])
                    if orders:
                        status = orders[0].get("orderStatus")
                        if status in ["Filled", "Cancelled", "Rejected"]:
                            return status == "Filled"
                
                time.sleep(0.5)
            except Exception as e:
                print(f"Wait for fill error: {e}")
                time.sleep(0.5)
        
        return False
    
    return _wait
