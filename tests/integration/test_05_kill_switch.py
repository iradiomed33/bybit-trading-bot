"""
Сценарий 5: Kill-Switch Closes Position

Проверяет:
- Открытие позиции
- Активацию kill-switch
- Закрытие позиции и отмену ордеров
"""

import pytest
import time
from conftest import skip_without_testnet


@skip_without_testnet
def test_kill_switch_scenario(
    rest_client,
    order_manager,
    kill_switch,
    database,
    testnet_config,
):
    """
    Тест kill-switch
    
    1. Открываем позицию
    2. Создаём limit ордера
    3. Активируем kill-switch
    4. Проверяем что позиция закрыта
    5. Проверяем что ордера отменены
    6. Проверяем флаг trading_disabled
    """
    symbol = testnet_config["symbol"]
    
    print("\n1. Открытие позиции...")
    
    result = order_manager.create_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        order_type="Market",
        qty=0.001,
        time_in_force="IOC",
    )
    
    assert result.success, f"Failed to open position: {result.error}"
    print("  ✓ Position opened")
    
    time.sleep(2)
    
    # Создаём limit ордер
    print("2. Создание limit ордера...")
    
    response = rest_client.post(
        "/v5/market/tickers",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    tickers = response.get("result", {}).get("list", [])
    current_price = float(tickers[0].get("lastPrice", 0))
    
    result = order_manager.create_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        order_type="Limit",
        qty=0.001,
        price=round(current_price * 0.8, 2),
        time_in_force="GTC",
    )
    
    assert result.success, "Failed to create limit order"
    print("  ✓ Limit order created")
    
    time.sleep(1)
    
    # Активация kill-switch
    print("3. Активация kill-switch...")
    
    kill_switch.activate("Integration test")
    print("  ✓ Kill-switch activated")
    
    time.sleep(3)  # Даём время на закрытие
    
    # Проверка что позиция закрыта
    print("4. Проверка позиции...")
    
    response = rest_client.post(
        "/v5/position/list",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    positions = response.get("result", {}).get("list", [])
    
    if positions:
        size = float(positions[0].get("size", 0))
        # Позиция должна быть 0 или очень маленькой (из-за округления)
        assert size < 0.0001, f"Position not closed: size={size}"
        print(f"  ✓ Position closed (size={size})")
    else:
        print("  ✓ No position (fully closed)")
    
    # Проверка что ордера отменены
    print("5. Проверка ордеров...")
    
    response = rest_client.post(
        "/v5/order/realtime",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    open_orders = response.get("result", {}).get("list", [])
    assert len(open_orders) == 0, f"Orders not cancelled: {len(open_orders)} orders"
    print("  ✓ All orders cancelled")
    
    # Проверка флага trading_disabled
    print("6. Проверка trading_disabled флага...")
    
    trading_disabled = database.get_config("trading_disabled", "false")
    assert trading_disabled == "true", "trading_disabled flag not set"
    print("  ✓ trading_disabled=true")
    
    # Сброс флага для следующих тестов
    database.save_config("trading_disabled", "false")
    print("  ✓ Flag reset for cleanup")
