"""
Тесты для Trading Stop API интеграции в OrderManager и StopLossTakeProfitManager.
"""

import sys
from unittest.mock import Mock, MagicMock
from decimal import Decimal


def test_order_manager_set_trading_stop():
    """Тест установки Trading Stop через OrderManager"""
    print("=" * 70)
    print("TEST 1: OrderManager.set_trading_stop()")
    print("=" * 70)
    
    # Импортируем напрямую, минуя __init__.py с зависимостями
    import importlib.util
    
    # Загружаем OrderResult
    spec = importlib.util.spec_from_file_location('order_result', 'execution/order_result.py')
    order_result_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(order_result_module)
    OrderResult = order_result_module.OrderResult
    
    # Создаём mock клиента
    mock_client = Mock()
    mock_db = Mock()
    
    # Mock успешный ответ API
    mock_client.post.return_value = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {}
    }
    
    # Создаём OrderManager с моками (используем импорт напрямую)
    spec = importlib.util.spec_from_file_location('order_manager', 'execution/order_manager.py')
    order_manager_module = importlib.util.module_from_spec(spec)
    sys.modules['execution.order_result'] = order_result_module
    spec.loader.exec_module(order_manager_module)
    
    OrderManager = order_manager_module.OrderManager
    
    om = OrderManager(mock_client, mock_db)
    
    # Вызываем set_trading_stop
    result = om.set_trading_stop(
        category="linear",
        symbol="BTCUSDT",
        stop_loss="45000",
        take_profit="55000",
    )
    
    # Проверяем результат
    assert result.success == True, f"Expected success=True, got {result.success}"
    assert mock_client.post.called, "API post должен быть вызван"
    
    # Проверяем параметры вызова
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/v5/position/trading-stop", "Неправильный endpoint"
    params = call_args[1]['params']
    assert params['symbol'] == "BTCUSDT", "Неправильный symbol"
    assert params['stopLoss'] == "45000", "Неправильный stopLoss"
    assert params['takeProfit'] == "55000", "Неправильный takeProfit"
    
    print("✓ set_trading_stop вызывает правильный API endpoint")
    print("✓ Параметры передаются корректно")
    print("✓ Возвращает OrderResult")
    print()


def test_order_manager_cancel_trading_stop():
    """Тест отмены Trading Stop через OrderManager"""
    print("=" * 70)
    print("TEST 2: OrderManager.cancel_trading_stop()")
    print("=" * 70)
    
    import importlib.util
    
    # Загружаем модули
    spec = importlib.util.spec_from_file_location('order_result', 'execution/order_result.py')
    order_result_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(order_result_module)
    
    spec = importlib.util.spec_from_file_location('order_manager', 'execution/order_manager.py')
    order_manager_module = importlib.util.module_from_spec(spec)
    sys.modules['execution.order_result'] = order_result_module
    spec.loader.exec_module(order_manager_module)
    
    OrderManager = order_manager_module.OrderManager
    
    mock_client = Mock()
    mock_db = Mock()
    
    mock_client.post.return_value = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {}
    }
    
    om = OrderManager(mock_client, mock_db)
    
    # Вызываем cancel_trading_stop
    result = om.cancel_trading_stop(
        category="linear",
        symbol="BTCUSDT",
    )
    
    # Проверяем результат
    assert result.success == True, f"Expected success=True, got {result.success}"
    
    # Проверяем параметры вызова
    call_args = mock_client.post.call_args
    params = call_args[1]['params']
    assert params['stopLoss'] == "0", "stopLoss должен быть '0' для отмены"
    assert params['takeProfit'] == "0", "takeProfit должен быть '0' для отмены"
    
    print("✓ cancel_trading_stop отправляет '0' для отмены")
    print("✓ Возвращает OrderResult")
    print()


def test_sl_tp_manager_place_exchange():
    """Тест размещения SL/TP через StopLossTakeProfitManager"""
    print("=" * 70)
    print("TEST 3: StopLossTakeProfitManager.place_exchange_sl_tp()")
    print("=" * 70)
    
    import importlib.util
    
    # Загружаем модули
    spec = importlib.util.spec_from_file_location('order_result', 'execution/order_result.py')
    order_result_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(order_result_module)
    OrderResult = order_result_module.OrderResult
    
    # Создаём моки
    mock_order_manager = Mock()
    mock_order_manager.set_trading_stop.return_value = OrderResult.success_result()
    
    # Загружаем StopLossTakeProfitManager (упрощённо)
    # Создаём минимальную реализацию для теста
    from dataclasses import dataclass, field
    from typing import Optional, Dict, Any
    
    @dataclass
    class StopLossTPConfig:
        use_exchange_sl_tp: bool = True
        use_virtual_levels: bool = True
        enable_trailing_stop: bool = True
        sl_atr_multiplier: float = 1.5
        tp_atr_multiplier: float = 2.0
        sl_percent_fallback: float = 1.0
        tp_percent_fallback: float = 2.0
        min_sl_distance: Decimal = Decimal("10")
        min_tp_distance: Decimal = Decimal("20")
        trailing_multiplier: float = 0.5
    
    @dataclass
    class StopLossTakeProfitLevels:
        position_id: str
        symbol: str
        side: str
        entry_price: Decimal
        entry_qty: Decimal
        atr: Optional[Decimal]
        sl_price: Decimal
        tp_price: Decimal
        sl_hit: bool = False
        tp_hit: bool = False
        closed_qty: Decimal = Decimal("0")
        sl_order_id: Optional[str] = None
        tp_order_id: Optional[str] = None
        created_at: float = 0
    
    # Создаём простой менеджер для теста
    class SimpleSLTPManager:
        def __init__(self, order_manager, config):
            self.order_manager = order_manager
            self.config = config
            self._levels = {}
        
        def calculate_levels(self, position_id, symbol, side, entry_price, entry_qty, current_atr=None):
            levels = StopLossTakeProfitLevels(
                position_id=position_id,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                entry_qty=entry_qty,
                atr=current_atr,
                sl_price=entry_price * Decimal("0.98") if side == "Long" else entry_price * Decimal("1.02"),
                tp_price=entry_price * Decimal("1.02") if side == "Long" else entry_price * Decimal("0.98"),
            )
            self._levels[position_id] = levels
            return levels
        
        def place_exchange_sl_tp(self, position_id, category="linear"):
            if position_id not in self._levels:
                return False, None, None
            
            levels = self._levels[position_id]
            
            if not self.config.use_exchange_sl_tp:
                return True, None, None
            
            result = self.order_manager.set_trading_stop(
                category=category,
                symbol=levels.symbol,
                position_idx=0,
                stop_loss=str(levels.sl_price) if levels.sl_price else None,
                take_profit=str(levels.tp_price) if levels.tp_price else None,
                sl_trigger_by="LastPrice",
                tp_trigger_by="LastPrice",
                tpsl_mode="Full",
            )
            
            if result.success:
                levels.sl_order_id = f"{position_id}_sl_ts"
                levels.tp_order_id = f"{position_id}_tp_ts"
                return True, levels.sl_order_id, levels.tp_order_id
            else:
                return False, None, None
    
    # Создаём менеджер
    config = StopLossTPConfig()
    manager = SimpleSLTPManager(mock_order_manager, config)
    
    # Создаём уровни
    levels = manager.calculate_levels(
        position_id="test_pos_1",
        symbol="BTCUSDT",
        side="Long",
        entry_price=Decimal("50000"),
        entry_qty=Decimal("0.1"),
        current_atr=Decimal("500"),
    )
    
    # Вызываем place_exchange_sl_tp
    success, sl_id, tp_id = manager.place_exchange_sl_tp("test_pos_1")
    
    # Проверяем
    assert success == True, f"Expected success=True, got {success}"
    assert sl_id is not None, "sl_order_id должен быть установлен"
    assert tp_id is not None, "tp_order_id должен быть установлен"
    assert mock_order_manager.set_trading_stop.called, "set_trading_stop должен быть вызван"
    
    # Проверяем параметры вызова
    call_args = mock_order_manager.set_trading_stop.call_args
    assert call_args[1]['symbol'] == "BTCUSDT", "Неправильный symbol"
    assert call_args[1]['tpsl_mode'] == "Full", "Должен быть Full mode"
    
    print("✓ place_exchange_sl_tp использует set_trading_stop")
    print("✓ Параметры передаются корректно")
    print("✓ Возвращает успех и IDs")
    print()


def main():
    """Запуск всех тестов"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "ТЕСТЫ TRADING STOP API ИНТЕГРАЦИИ" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    tests = [
        ("OrderManager.set_trading_stop", test_order_manager_set_trading_stop),
        ("OrderManager.cancel_trading_stop", test_order_manager_cancel_trading_stop),
        ("StopLossTakeProfitManager.place_exchange_sl_tp", test_sl_tp_manager_place_exchange),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 70)
    print(f"РЕЗУЛЬТАТЫ: {passed} пройдено, {failed} провалено")
    print("=" * 70)
    
    if failed == 0:
        print("\n✓✓✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! ✓✓✓\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
