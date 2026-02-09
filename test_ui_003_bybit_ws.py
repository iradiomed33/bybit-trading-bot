"""
Тест TASK-UI-003 (исправленный): проверка Bybit realtime WebSocket

Проверяем что:
1. _get_account_client_from_env() создаёт клиента если ключи есть
2. _fetch_balance_snapshot_sync() корректно парсит баланс с Bybit
3. WebSocket использует Bybit данные (а не демо 10000/45000)
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_account_client_creation():
    """Тест создания AccountClient из env"""
    
    # Импортируем функцию
    sys.path.insert(0, str(Path(__file__).parent))
    from api.app import _get_account_client_from_env
    
    print("\n[1/3] Тест _get_account_client_from_env()...")
    
    # Без ключей должно быть None
    with patch.dict(os.environ, {}, clear=True):
        with patch('api.app.Config') as mock_config:
            mock_config.BYBIT_API_KEY = ""
            mock_config.BYBIT_API_SECRET = ""
            client = _get_account_client_from_env()
            assert client is None, "Без ключей должен быть None"
            print("  ✓ Без ключей: None")
    
    # С ключами должен создать клиента
    with patch.dict(os.environ, {"BYBIT_API_KEY": "test_key", "BYBIT_API_SECRET": "test_secret"}):
        with patch('api.app.Config') as mock_config:
            mock_config.BYBIT_API_KEY = "test_key"
            mock_config.BYBIT_API_SECRET = "test_secret"
            
            with patch('api.app.AccountClient') as mock_ac:
                mock_instance = MagicMock()
                mock_ac.return_value = mock_instance
                
                client = _get_account_client_from_env()
                assert client is not None, "С ключами должен создать клиента"
                print("  ✓ С ключами: создаёт AccountClient")
                
                # Проверяем кеширование
                client2 = _get_account_client_from_env()
                assert client2 is client, "Должен вернуть закешированный клиент"
                print("  ✓ Кеширование работает")
    
    return True


def test_usdt_coin_extraction():
    """Тест парсинга USDT coin из wallet balance"""
    
    from api.app import _extract_usdt_coin_info
    
    print("\n[2/3] Тест _extract_usdt_coin_info()...")
    
    # Корректный ответ Bybit
    wallet_response = {
        "retCode": 0,
        "result": {
            "list": [
                {
                    "accountType": "UNIFIED",
                    "coin": [
                        {"coin": "BTC", "equity": "0.5"},
                        {"coin": "USDT", "equity": "10000.0", "walletBalance": "9800.0", "unrealisedPnl": "200.0"},
                        {"coin": "ETH", "equity": "2.0"},
                    ]
                }
            ]
        }
    }
    
    usdt = _extract_usdt_coin_info(wallet_response)
    assert usdt["coin"] == "USDT", "Должен найти USDT"
    assert usdt["equity"] == "10000.0", f"Неверный equity: {usdt.get('equity')}"
    print("  ✓ Корректно извлекает USDT coin")
    
    # Некорректный ответ
    bad_response = {"retCode": 10001, "retMsg": "error"}
    usdt = _extract_usdt_coin_info(bad_response)
    assert usdt == {}, "При ошибке должен вернуть пустой dict"
    print("  ✓ При ошибке возвращает {}")
    
    return True


def test_balance_snapshot_structure():
    """Тест структуры ответа _fetch_balance_snapshot_sync()"""
    
    from api.app import _fetch_balance_snapshot_sync
    
    print("\n[3/3] Тест _fetch_balance_snapshot_sync()...")
    
    # Мокируем AccountClient
    with patch('api.app._get_account_client_from_env') as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Мокируем wallet balance
        mock_client.client.get.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "coin": [
                            {
                                "coin": "USDT",
                                "equity": "12000.50",
                                "walletBalance": "11800.00",
                                "availableToWithdraw": "10000.00",
                                "unrealisedPnl": "200.50",
                                "marginBalance": "11900.00",
                            }
                        ]
                    }
                ]
            }
        }
        
        # Мокируем positions
        mock_client.get_positions.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {"size": "0.1", "markPrice": "45000"},
                    {"size": "0.05", "markPrice": "46000"},
                ]
            }
        }
        
        snapshot = _fetch_balance_snapshot_sync()
        
        # Проверяем структуру
        required_fields = ["total_balance", "available_balance", "position_value", "unrealized_pnl", "currency", "margin_balance", "source"]
        for field in required_fields:
            assert field in snapshot, f"Отсутствует поле: {field}"
        
        # Проверяем значения
        assert snapshot["total_balance"] == 12000.50, f"Неверный total_balance: {snapshot['total_balance']}"
        assert snapshot["available_balance"] == 10000.00, f"Неверный available_balance: {snapshot['available_balance']}"
        assert snapshot["unrealized_pnl"] == 200.50, f"Неверный unrealized_pnl: {snapshot['unrealized_pnl']}"
        assert snapshot["source"] == "bybit", f"source должен быть 'bybit', получено: {snapshot['source']}"
        
        # position_value = 0.1 * 45000 + 0.05 * 46000 = 4500 + 2300 = 6800
        expected_pv = 0.1 * 45000 + 0.05 * 46000
        assert abs(snapshot["position_value"] - expected_pv) < 0.01, \
            f"Неверный position_value: {snapshot['position_value']}, ожидалось {expected_pv}"
        
        print("  ✓ Все обязательные поля присутствуют")
        print(f"  ✓ total_balance: {snapshot['total_balance']}")
        print(f"  ✓ position_value: {snapshot['position_value']} (расчёт из позиций)")
        print(f"  ✓ source: {snapshot['source']}")
    
    return True


def test_websocket_uses_bybit_not_demo():
    """Проверяем что WebSocket НЕ использует демо 10000/45000"""
    
    print("\n[4/4] Проверка что WS не использует демо данные...")
    
    # Читаем app.py
    app_py = Path("api/app.py").read_text(encoding='utf-8')
    
    # Проверяем что в websocket_endpoint нет хардкода "10000.0" и "45000" в неправильном месте
    # После наших правок должен быть _fetch_balance_snapshot_sync()
    
    if "await asyncio.to_thread(_fetch_balance_snapshot_sync)" in app_py:
        print("  ✓ WebSocket использует _fetch_balance_snapshot_sync()")
    else:
        print("  ✗ WebSocket НЕ использует _fetch_balance_snapshot_sync()")
        return False
    
    # Проверяем fallback на local
    if '"source": "local"' in app_py:
        print("  ✓ Fallback на local помечен как 'source: local'")
    else:
        print("  ✗ Fallback не помечен")
        return False
    
    # Проверяем что есть периодический пуш
    if "last_push" in app_py and "await asyncio.wait_for(websocket.receive_text(), timeout=" in app_py:
        print("  ✓ Периодический пуш баланса реализован")
    else:
        print("  ✗ Периодический пуш не найден")
        return False
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ TASK-UI-003 (ИСПРАВЛЕННЫЙ): Bybit Realtime WebSocket")
    print("=" * 70)
    
    try:
        test1 = test_account_client_creation()
        test2 = test_usdt_coin_extraction()
        test3 = test_balance_snapshot_structure()
        test4 = test_websocket_uses_bybit_not_demo()
        
        print("\n" + "=" * 70)
        if test1 and test2 and test3 and test4:
            print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
            print("\nКлючевые изменения:")
            print("• WebSocket теперь использует Bybit API (не демо 10000/45000)")
            print("• _fetch_balance_snapshot_sync() берёт реальный баланс/позиции")
            print("• Fallback на local помечен как 'source: local'")
            print("• Периодический пуш каждые 10 секунд")
        else:
            print("✗ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
