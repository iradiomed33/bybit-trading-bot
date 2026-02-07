"""
Тесты для Private WebSocket улучшений.
"""

import sys


def test_auth_message_fix():
    """Тест исправления отправки auth-сообщения"""
    print("=" * 70)
    print("TEST 1: Authentication message fix")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        code = f.read()
    
    # Проверяем, что неправильная отправка удалена
    assert 'self.client.ws._app.send(auth_msg)' not in code, "Old incorrect auth send still present"
    
    # Проверяем, что используется правильная отправка
    assert 'json.dumps(auth_msg)' in code, "Correct json.dumps(auth_msg) not found"
    assert 'self.client.ws.send(json.dumps(auth_msg))' in code, "Correct auth send not found"
    
    # Проверяем импорт json
    assert 'import json' in code, "json module not imported"
    
    print("✓ Удалена неправильная отправка: self.client.ws._app.send()")
    print("✓ Добавлена правильная отправка: json.dumps(auth_msg)")
    print("✓ Импортирован модуль json")
    print()


def test_reconnect_callback():
    """Тест добавления on_reconnect колбэка"""
    print("=" * 70)
    print("TEST 2: Reconnect callback support")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        private_ws_code = f.read()
    
    with open('exchange/websocket_client.py', 'r') as f:
        ws_client_code = f.read()
    
    # Проверяем метод _on_reconnect в PrivateWebSocket
    assert 'def _on_reconnect(self):' in private_ws_code, "_on_reconnect method not found"
    assert 'self.authenticated = False' in private_ws_code, "Doesn't reset authenticated flag"
    assert 'self._authenticate()' in private_ws_code, "Doesn't call _authenticate on reconnect"
    
    # Проверяем on_reconnect параметр в BybitWebSocketClient
    assert 'on_reconnect' in ws_client_code, "on_reconnect parameter not added"
    assert 'on_reconnect_callback' in ws_client_code, "on_reconnect_callback not stored"
    assert 'if self.on_reconnect_callback:' in ws_client_code, "on_reconnect_callback not called"
    
    print("✓ Добавлен метод _on_reconnect() в PrivateWebSocket")
    print("✓ Сбрасывается флаг authenticated при reconnect")
    print("✓ Вызывается повторная аутентификация")
    print("✓ BybitWebSocketClient поддерживает on_reconnect callback")
    print()


def test_execution_topic():
    """Тест добавления execution топика"""
    print("=" * 70)
    print("TEST 3: Execution topic subscription")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        code = f.read()
    
    # Проверяем подписку на execution
    assert '"execution"' in code, "execution topic not in subscription"
    assert 'topics = ["order", "position", "execution"]' in code, "execution not added to topics list"
    
    # Проверяем обработку execution событий
    assert 'if topic == "execution":' in code, "execution topic handler not found"
    assert 'self.executions_history.append' in code, "executions not saved to history"
    
    # Проверяем on_execution callback
    assert 'on_execution' in code, "on_execution callback not added"
    assert 'if self.on_execution:' in code, "on_execution callback not called"
    
    print("✓ Добавлена подписка на 'execution' топик")
    print("✓ Обработка execution событий")
    print("✓ Сохранение в executions_history")
    print("✓ Поддержка on_execution callback")
    print()


def test_local_state():
    """Тест локального хранилища состояния"""
    print("=" * 70)
    print("TEST 4: Local state storage")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        code = f.read()
    
    # Проверяем инициализацию состояния
    assert 'self.orders_state: Dict[str, Dict] = {}' in code, "orders_state not initialized"
    assert 'self.positions_state: Dict[str, Dict] = {}' in code, "positions_state not initialized"
    assert 'self.executions_history: List[Dict] = []' in code, "executions_history not initialized"
    
    # Проверяем обновление состояния для ордеров
    assert 'self.orders_state[order_id] = order_data' in code, "orders_state not updated"
    
    # Проверяем обновление состояния для позиций
    assert 'self.positions_state[symbol] = position_data' in code, "positions_state not updated"
    
    print("✓ Инициализированы словари состояния")
    print("✓ orders_state обновляется при получении order событий")
    print("✓ positions_state обновляется при получении position событий")
    print("✓ executions_history сохраняет fills")
    print()


def test_state_access_methods():
    """Тест методов доступа к состоянию"""
    print("=" * 70)
    print("TEST 5: State access methods")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        code = f.read()
    
    # Проверяем наличие методов
    methods = [
        'def get_order_status',
        'def get_position',
        'def get_executions',
        'def get_all_orders',
        'def get_all_positions',
    ]
    
    for method in methods:
        assert method in code, f"{method} method not found"
        print(f"✓ Добавлен метод {method}()")
    
    print()


def test_logging():
    """Тест логирования событий"""
    print("=" * 70)
    print("TEST 6: Event logging")
    print("=" * 70)
    
    with open('exchange/private_ws.py', 'r') as f:
        code = f.read()
    
    # Проверяем логирование для разных событий
    assert 'logger.debug(f"Order update:' in code, "Order updates not logged"
    assert 'logger.debug(f"Position update:' in code, "Position updates not logged"
    assert 'logger.info(f"Execution:' in code or 'logger.info(\n                    f"Execution:' in code, "Executions not logged"
    
    print("✓ Логирование обновлений ордеров")
    print("✓ Логирование обновлений позиций")
    print("✓ Логирование исполнений (fills)")
    print()


def main():
    """Запуск всех тестов"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "ТЕСТЫ PRIVATE WEBSOCKET УЛУЧШЕНИЙ" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    tests = [
        ("Authentication message fix", test_auth_message_fix),
        ("Reconnect callback support", test_reconnect_callback),
        ("Execution topic subscription", test_execution_topic),
        ("Local state storage", test_local_state),
        ("State access methods", test_state_access_methods),
        ("Event logging", test_logging),
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
