"""
Сценарий 3: Set SL/TP → Trigger

Проверяет:
- Установку Trading Stop (SL/TP)
- Проверку через API
- Отмену SL/TP
"""

import pytest
import time
from decimal import Decimal
from conftest import skip_without_testnet


@skip_without_testnet
def test_sltp_management(
    rest_client,
    order_manager,
    testnet_config,
    cleanup_positions,
):
    """
    Тест установки и отмены SL/TP
    
    1. Открываем минимальную позицию
    2. Устанавливаем SL/TP через set_trading_stop
    3. Проверяем что SL/TP установлены
    4. Отменяем SL/TP
    5. Закрываем позицию
    """
    symbol = testnet_config["symbol"]
    min_qty = 0.001
    
    print(f"\n1. Открытие позиции {symbol}")
    
    # Открываем позицию
    result = order_manager.create_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        order_type="Market",
        qty=min_qty,
        time_in_force="IOC",
    )
    
    assert result.success, f"Failed to open position: {result.error}"
    print(f"✓ Position opened")
    
    time.sleep(2)  # Ждём исполнения
    
    # Получаем текущую цену для расчёта SL/TP
    print("2. Получение текущей цены...")
    response = rest_client.post(
        "/v5/market/tickers",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    assert response.get("retCode") == 0, "Failed to get ticker"
    
    tickers = response.get("result", {}).get("list", [])
    assert len(tickers) > 0, "No ticker data"
    
    mark_price = float(tickers[0].get("markPrice", 0))
    assert mark_price > 0, "Invalid mark price"
    
    # SL на 5% ниже, TP на 5% выше
    stop_loss = str(round(mark_price * 0.95, 2))
    take_profit = str(round(mark_price * 1.05, 2))
    
    print(f"  Mark Price: {mark_price}")
    print(f"  SL: {stop_loss}")
    print(f"  TP: {take_profit}")
    
    # Установка SL/TP
    print("3. Установка Trading Stop...")
    result = order_manager.set_trading_stop(
        category="linear",
        symbol=symbol,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_idx=0,
    )
    
    assert result.success, f"Failed to set SL/TP: {result.error}"
    print("✓ SL/TP установлены")
    
    # Проверка что SL/TP установлены
    print("4. Проверка SL/TP...")
    time.sleep(1)
    
    response = rest_client.post(
        "/v5/position/list",
        params={
            "category": "linear",
            "symbol": symbol,
        }
    )
    
    positions = response.get("result", {}).get("list", [])
    assert len(positions) > 0
    
    position = positions[0]
    assert position.get("stopLoss") == stop_loss, "SL not set correctly"
    assert position.get("takeProfit") == take_profit, "TP not set correctly"
    print("✓ SL/TP проверены через API")
    
    # Отмена SL/TP
    print("5. Отмена SL/TP...")
    result = order_manager.cancel_trading_stop(
        category="linear",
        symbol=symbol,
        position_idx=0,
    )
    
    assert result.success, f"Failed to cancel SL/TP: {result.error}"
    print("✓ SL/TP отменены")
    
    # Cleanup
    print("6. Cleanup...")
    cleanup_positions()
    print("✓ Position closed")
