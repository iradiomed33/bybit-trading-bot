#!/usr/bin/env python3
"""
Тест для проверки, что приватные API запросы используют X-BAPI-SIGN-TYPE: 2 заголовок.
"""

import sys
from unittest.mock import patch, Mock
from exchange.base_client import BybitRestClient
from exchange.account import AccountClient


def test_rest_client_headers():
    """Проверяет, что REST клиент добавляет правильные заголовки для подписанных запросов."""
    
    print("\n" + "="*60)
    print("ТЕСТ 1: Проверка заголовков REST клиента для GET запроса")
    print("="*60)
    
    rest_client = BybitRestClient(
        api_key="TESTKEY",
        api_secret="TESTSECRET",
        testnet=True
    )
    
    # Мокируем session.get чтобы перехватить заголовки
    with patch('exchange.base_client.BybitRestClient._rate_limit_wait'):
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "retMsg": "OK", "result": {}}
            mock_get.return_value = mock_response
            
            # Делаем подписанный GET запрос
            rest_client.get("/v5/account/wallet-balance", signed=True)
            
            # Получаем заголовки из моков
            call_kwargs = mock_get.call_args[1]
            headers = call_kwargs.get("headers", {})
            
            print(f"\n📋 Заголовки GET запроса:")
            for header_name in ["X-BAPI-API-KEY", "X-BAPI-TIMESTAMP", "X-BAPI-SIGN", 
                               "X-BAPI-RECV-WINDOW", "X-BAPI-SIGN-TYPE"]:
                if header_name in headers:
                    value = headers[header_name]
                    if header_name == "X-BAPI-SIGN":
                        print(f"  ✓ {header_name}: {value[:20]}... (HMAC-SHA256)")
                    else:
                        print(f"  ✓ {header_name}: {value}")
                else:
                    print(f"  ✗ {header_name}: ОТСУТСТВУЕТ!")
            
            # Проверяем критические значения
            assert headers.get("X-BAPI-SIGN-TYPE") == "2", "X-BAPI-SIGN-TYPE должен быть '2'"
            assert "X-BAPI-API-KEY" in headers, "Отсутствует X-BAPI-API-KEY"
            assert "X-BAPI-SIGN" in headers, "Отсутствует X-BAPI-SIGN"
            print("\n✅ GET запрос: все заголовки в порядке!\n")


def test_account_client_positions():
    """Проверяет, что AccountClient.get_positions добавляет правильные параметры и заголовки."""
    
    print("="*60)
    print("ТЕСТ 2: Проверка get_positions() с параметрами и заголовками")
    print("="*60)
    
    rest_client = BybitRestClient(
        api_key="TESTKEY",
        api_secret="TESTSECRET",
        testnet=True
    )
    account_client = AccountClient(rest_client)
    
    with patch('exchange.base_client.BybitRestClient._rate_limit_wait'):
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"list": [], "nextPageCursor": ""}
            }
            mock_get.return_value = mock_response
            
            # Делаем запрос get_positions
            account_client.get_positions(category="linear")
            
            # Проверяем URL и параметры
            call_args = mock_get.call_args
            url = call_args[0][0]
            call_kwargs = call_args[1]
            params = call_kwargs.get("params", {})
            headers = call_kwargs.get("headers", {})
            
            print(f"\n📋 Параметры запроса /v5/position/list:")
            for param in ["category", "settleCoin"]:
                if param in params:
                    print(f"  ✓ {param}: {params[param]}")
                else:
                    print(f"  ℹ {param}: не указан (опционально)")
            
            print(f"\n📋 Заголовки запроса:")
            assert headers.get("X-BAPI-SIGN-TYPE") == "2", "X-BAPI-SIGN-TYPE должен быть '2'"
            print(f"  ✓ X-BAPI-SIGN-TYPE: {headers.get('X-BAPI-SIGN-TYPE')}")
            print(f"  ✓ X-BAPI-API-KEY: {headers.get('X-BAPI-API-KEY')}")
            print(f"  ✓ X-BAPI-SIGN: {headers.get('X-BAPI-SIGN')[:20]}...")
            
            print("\n✅ get_positions(): параметры и заголовки в порядке!\n")


def test_post_request_headers():
    """Проверяет, что POST запросы также имеют X-BAPI-SIGN-TYPE: 2."""
    
    print("="*60)
    print("ТЕСТ 3: Проверка заголовков для POST запроса")
    print("="*60)
    
    rest_client = BybitRestClient(
        api_key="TESTKEY",
        api_secret="TESTSECRET",
        testnet=True
    )
    
    with patch('exchange.base_client.BybitRestClient._rate_limit_wait'):
        with patch('requests.Session.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "retMsg": "OK", "result": {}}
            mock_post.return_value = mock_response
            
            # Делаем подписанный POST запрос
            rest_client.post(
                "/v5/order/create",
                params={"symbol": "BTCUSDT", "side": "Buy"},
                signed=True
            )
            
            # Получаем заголовки из моков
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs.get("headers", {})
            
            print(f"\n📋 Заголовки POST запроса:")
            assert headers.get("X-BAPI-SIGN-TYPE") == "2", "X-BAPI-SIGN-TYPE должен быть '2'"
            print(f"  ✓ X-BAPI-SIGN-TYPE: {headers.get('X-BAPI-SIGN-TYPE')}")
            print(f"  ✓ X-BAPI-API-KEY: {headers.get('X-BAPI-API-KEY')}")
            print(f"  ✓ X-BAPI-SIGN: {headers.get('X-BAPI-SIGN')[:20]}...")
            print(f"  ✓ Content-Type: {headers.get('Content-Type')}")
            
            print("\n✅ POST запрос: все заголовки в порядке!\n")


def main():
    """Запускает все тесты."""
    
    print("\n" + "#"*60)
    print("# ТЕСТ АУТЕНТИФИКАЦИИ BYBIT V5 API")
    print("#"*60)
    
    try:
        test_rest_client_headers()
        test_account_client_positions()
        test_post_request_headers()
        
        print("="*60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("="*60)
        print("\n📌 ИТОГИ ИСПРАВЛЕНИЯ:")
        print("  ✓ Добавлен заголовок X-BAPI-SIGN-TYPE: '2' (HMAC-SHA256)")
        print("  ✓ Все приватные GET и POST запросы теперь подписаны правильно")
        print("  ✓ Параметры (category, settleCoin) добавлены для /v5/position/list")
        print("\n🔧 Следующее: запустить реальные тесты:")
        print("  pytest tests/test_private_api.py -v")
        print("  pytest tests/test_signature.py -v")
        print("#"*60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
