"""
Сценарий 4: Cancel All Orders

Проверяет:
- Создание нескольких limit ордеров
- Отмену всех через cancel_all_orders
"""

import pytest
import time
from conftest import skip_without_testnet


@skip_without_testnet
def test_cancel_all_orders(
    rest_client,
    order_manager,
    testnet_config,
    cleanup_orders,
):
    """
    Тест отмены всех ордеров
    
    1. Создаём 3 limit ордера далеко от цены
    2. Проверяем что они в списке открытых
    3. Отменяем все через cancel_all_orders
    4. Проверяем что список пуст
    """
    symbol = testnet_config["symbol"]
    
    # Получаем текущую цену
    print("\n1. Получение текущей цены...")
    response = rest_client.post(
        "/v5/market/tickers",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    tickers = response.get("result", {}).get("list", [])
    current_price = float(tickers[0].get("lastPrice", 0))
    print(f"  Current price: {current_price}")
    
    # Создаём 3 limit ордера далеко от цены (не исполнятся)
    print("2. Создание 3 limit ордеров...")
    
    orders_created = []
    for i in range(3):
        # Limit buy на 20% ниже текущей цены
        limit_price = round(current_price * 0.8, 2)
        
        result = order_manager.create_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            order_type="Limit",
            qty=0.001,
            price=limit_price,
            time_in_force="GTC",
        )
        
        assert result.success, f"Failed to create order {i+1}: {result.error}"
        orders_created.append(result.order_id)
        print(f"  ✓ Order {i+1} created: {result.order_id}")
        
        time.sleep(0.3)  # Небольшая задержка
    
    # Проверка что ордера в списке открытых
    print("3. Проверка открытых ордеров...")
    time.sleep(1)
    
    response = rest_client.post(
        "/v5/order/realtime",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    open_orders = response.get("result", {}).get("list", [])
    assert len(open_orders) >= 3, f"Expected >= 3 orders, got {len(open_orders)}"
    print(f"  ✓ Found {len(open_orders)} open orders")
    
    # Отмена всех ордеров
    print("4. Отмена всех ордеров...")
    result = order_manager.cancel_all_orders(
        category="linear",
        symbol=symbol,
    )
    
    assert result.success, f"Failed to cancel all orders: {result.error}"
    print("  ✓ cancel_all_orders успешно")
    
    # Проверка что ордеров не осталось
    print("5. Проверка что ордера отменены...")
    time.sleep(1)
    
    response = rest_client.post(
        "/v5/order/realtime",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    open_orders = response.get("result", {}).get("list", [])
    assert len(open_orders) == 0, f"Expected 0 orders, got {len(open_orders)}"
    print("  ✓ Все ордера отменены")
