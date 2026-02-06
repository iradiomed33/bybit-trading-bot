"""
Тесты для улучшенного Kill Switch Manager.
"""

import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


def test_kill_switch_init():
    """Тест инициализации KillSwitchManager с новыми параметрами"""
    print("=" * 70)
    print("TEST 1: KillSwitchManager initialization")
    print("=" * 70)
    
    # Создаём моки
    mock_client = Mock()
    mock_order_manager = Mock()
    mock_db = Mock()
    allowed_symbols = ["BTCUSDT", "ETHUSDT"]
    
    # Импортируем KillSwitchManager
    import importlib.util
    spec = importlib.util.spec_from_file_location('kill_switch', 'execution/kill_switch.py')
    kill_switch_module = importlib.util.module_from_spec(spec)
    
    # Создаём моки для зависимостей
    sys.modules['storage.database'] = Mock()
    sys.modules['logger'] = Mock()
    sys.modules['logger'].setup_logger = Mock(return_value=Mock())
    
    spec.loader.exec_module(kill_switch_module)
    
    KillSwitchManager = kill_switch_module.KillSwitchManager
    
    # Создаём manager
    manager = KillSwitchManager(
        client=mock_client,
        order_manager=mock_order_manager,
        db=mock_db,
        allowed_symbols=allowed_symbols,
    )
    
    # Проверяем
    assert manager.client == mock_client, "Client not set"
    assert manager.order_manager == mock_order_manager, "OrderManager not set"
    assert manager.db == mock_db, "Database not set"
    assert manager.allowed_symbols == allowed_symbols, "Allowed symbols not set"
    assert manager.is_halted == False, "Should start not halted"
    
    print("✓ KillSwitchManager инициализирован с новыми параметрами")
    print(f"✓ allowed_symbols: {allowed_symbols}")
    print()


def test_cancel_orders_with_order_manager():
    """Тест отмены ордеров через OrderManager"""
    print("=" * 70)
    print("TEST 2: Cancel orders through OrderManager")
    print("=" * 70)
    
    # Проверяем структуру кода
    with open('execution/kill_switch.py', 'r') as f:
        code = f.read()
    
    # Проверяем, что используется OrderManager
    assert 'self.order_manager.cancel_all_orders' in code, "Should use OrderManager.cancel_all_orders"
    assert 'result.success' in code, "Should check OrderResult.success"
    
    # Проверяем, что удалён хардкод
    assert '"BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"' not in code, "Hardcoded symbols should be removed"
    
    # Проверяем, что используются allowed_symbols или позиции
    assert 'self.allowed_symbols' in code, "Should use allowed_symbols"
    assert '_get_open_positions' in code, "Should get symbols from positions"
    
    print("✓ Используется OrderManager.cancel_all_orders()")
    print("✓ Проверяется result.success")
    print("✓ Хардкод символов удалён")
    print("✓ Символы берутся из allowed_symbols или позиций")
    print()


def test_close_positions_with_order_manager():
    """Тест закрытия позиций через OrderManager"""
    print("=" * 70)
    print("TEST 3: Close positions through OrderManager")
    print("=" * 70)
    
    with open('execution/kill_switch.py', 'r') as f:
        code = f.read()
    
    # Проверяем, что используется OrderManager
    assert 'self.order_manager.create_order' in code, "Should use OrderManager.create_order"
    assert 'order_type="Market"' in code, "Should use Market orders"
    assert 'time_in_force="IOC"' in code, "Should use IOC time in force"
    
    # Проверяем, что удалён старый метод
    assert 'self.client.place_order' not in code, "Should not use client.place_order"
    
    print("✓ Используется OrderManager.create_order()")
    print("✓ order_type='Market'")
    print("✓ time_in_force='IOC'")
    print("✓ Удалён client.place_order()")
    print()


def test_get_positions_api():
    """Тест получения позиций через правильный API"""
    print("=" * 70)
    print("TEST 4: Get positions through correct API")
    print("=" * 70)
    
    with open('execution/kill_switch.py', 'r') as f:
        code = f.read()
    
    # Проверяем, что используется правильный API
    assert '/v5/position/list' in code, "Should use /v5/position/list endpoint"
    assert 'client.post' in code, "Should use client.post"
    
    # Проверяем, что удалён старый метод
    assert 'client.get_positions()' not in code, "Should not use client.get_positions()"
    
    print("✓ Используется /v5/position/list endpoint")
    print("✓ Используется client.post()")
    print("✓ Удалён client.get_positions()")
    print()


def test_trading_disabled_flag():
    """Тест флага trading_disabled в БД"""
    print("=" * 70)
    print("TEST 5: trading_disabled flag in database")
    print("=" * 70)
    
    with open('execution/kill_switch.py', 'r') as f:
        code = f.read()
    
    # Проверяем сохранение флага при активации
    assert 'db.save_config("trading_disabled", True)' in code, "Should save trading_disabled=True on activate"
    
    # Проверяем проверку флага в can_trade
    assert 'db.get_config("trading_disabled"' in code, "Should check trading_disabled in can_trade"
    
    # Проверяем сброс флага в reset
    assert 'db.save_config("trading_disabled", False)' in code, "Should clear trading_disabled on reset"
    
    print("✓ activate() сохраняет trading_disabled=True")
    print("✓ can_trade() проверяет флаг из БД")
    print("✓ reset() сбрасывает trading_disabled=False")
    print()


def test_tradingbot_integration():
    """Тест интеграции с TradingBot"""
    print("=" * 70)
    print("TEST 6: TradingBot integration")
    print("=" * 70)
    
    with open('bot/trading_bot.py', 'r') as f:
        code = f.read()
    
    # Проверяем, что передаются все параметры
    assert 'order_manager=self.order_manager' in code, "Should pass order_manager"
    assert 'db=self.db' in code, "Should pass db"
    assert 'allowed_symbols=' in code, "Should pass allowed_symbols"
    
    print("✓ TradingBot передаёт order_manager")
    print("✓ TradingBot передаёт db")
    print("✓ TradingBot передаёт allowed_symbols")
    print()


def main():
    """Запуск всех тестов"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "ТЕСТЫ KILL SWITCH MANAGER" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    tests = [
        ("KillSwitchManager initialization", test_kill_switch_init),
        ("Cancel orders through OrderManager", test_cancel_orders_with_order_manager),
        ("Close positions through OrderManager", test_close_positions_with_order_manager),
        ("Get positions through correct API", test_get_positions_api),
        ("trading_disabled flag in database", test_trading_disabled_flag),
        ("TradingBot integration", test_tradingbot_integration),
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
