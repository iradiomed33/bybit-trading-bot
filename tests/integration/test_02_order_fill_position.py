"""
Сценарий 2: Place Order → Fill → Position Updated

Проверяет:
- Размещение Market ордера
- Получение fill
- Обновление позиции
"""

import pytest
import time
from decimal import Decimal
from conftest import skip_without_testnet


@skip_without_testnet
def test_order_fill_and_position(
    rest_client,
    order_manager,
    position_manager,
    testnet_config,
    cleanup_positions,
    cleanup_orders,
    wait_for_fill
):
    """
    Тест полного цикла: ордер → fill → позиция
    
    1. Размещаем минимальный Market ордер
    2. Ждём fill
    3. Проверяем что позиция обновилась
    4. Закрываем позицию
    """
    symbol = testnet_config["symbol"]
    
    # Минимальный qty для BTCUSDT на testnet обычно 0.001
    min_qty = 0.001
    
    print(f"\n1. Размещение Market ордера {symbol} qty={min_qty}")
    
    # Создание ордера через OrderManager
    result = order_manager.create_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        order_type="Market",
        qty=min_qty,
        time_in_force="IOC",
    )
    
    # Проверка что ордер создан
    assert result.success, f"Order failed: {result.error}"
    assert result.order_id is not None, "Order ID is None"
    
    order_id = result.order_id
    print(f"✓ Order created: {order_id}")
    
    # Ждём fill (Market ордер должен исполниться быстро)
    print("2. Ожидание fill...")
    is_filled = wait_for_fill(rest_client, order_id, max_wait=10)
    
    assert is_filled, "Order was not filled in time"
    print("✓ Order filled")
    
    # Проверка позиции через API
    print("3. Проверка позиции...")
    time.sleep(1)  # Даём время на обновление
    
    response = rest_client.post(
        "/v5/position/list",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    assert response.get("retCode") == 0, "Failed to get position"
    
    positions = response.get("result", {}).get("list", [])
    assert len(positions) > 0, "No position found"
    
    position = positions[0]
    size = float(position.get("size", 0))
    
    assert size > 0, f"Position size is {size}, expected > 0"
    print(f"✓ Position updated: size={size}")
    
    # Закрытие позиции через cleanup
    print("4. Cleanup - закрытие позиции...")
    cleanup_positions()
    print("✓ Position closed")
