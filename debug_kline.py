#!/usr/bin/env python3
"""
Диагностика проблемы с kline endpoint
"""
import requests
import json
from config import Config


def test_kline_direct():
    """Тест kline endpoint напрямую через requests"""
    print("=" * 70)
    print("ТЕСТ 1: Прямой запрос kline (без авторизации)")
    print("=" * 70)
    
    url = "https://api-testnet.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": "BTCUSDT",
        "interval": "60",
        "limit": 5
    }
    
    print(f"\nURL: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\nHTTP Status: {response.status_code}")
        print(f"Headers sent:")
        for k, v in response.request.headers.items():
            print(f"  {k}: {v}")
        
        data = response.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2)[:500])
        
        if data.get("retCode") == 0:
            print("\n✅ Успех!")
            candles_count = len(data.get("result", {}).get("list", []))
            print(f"Получено свечей: {candles_count}")
        else:
            print(f"\n❌ Ошибка: {data.get('retCode')} - {data.get('retMsg')}")
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_kline_with_our_client():
    """Тест kline через наш MarketDataClient"""
    print("\n" + "=" * 70)
    print("ТЕСТ 2: Через MarketDataClient")
    print("=" * 70)
    
    from exchange.market_data import MarketDataClient
    
    client = MarketDataClient(testnet=True)
    
    print(f"\nAPI Key present: {bool(client.client.api_key)}")
    print(f"API Secret present: {bool(client.client.api_secret)}")
    print(f"Base URL: {client.client.base_url}")
    
    try:
        response = client.get_kline(
            symbol="BTCUSDT",
            interval="60",
            limit=5
        )
        
        if response.get("retCode") == 0:
            print("\n✅ Успех!")
            candles_count = len(response.get("result", {}).get("list", []))
            print(f"Получено свечей: {candles_count}")
        else:
            print(f"\n❌ Ошибка: {response.get('retCode')} - {response.get('retMsg')}")
            print(f"Full response: {json.dumps(response, indent=2)[:500]}")
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_all_symbols():
    """Тест всех символов напрямую"""
    print("\n" + "=" * 70)
    print("ТЕСТ 3: Все символы напрямую")
    print("=" * 70)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    url = "https://api-testnet.bybit.com/v5/market/kline"
    
    for symbol in symbols:
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": "60",
            "limit": 1
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get("retCode") == 0:
                print(f"  {symbol}: ✅ OK")
            else:
                print(f"  {symbol}: ❌ {data.get('retMsg')}")
        except Exception as e:
            print(f"  {symbol}: ❌ {str(e)[:50]}")


def check_authentication_headers():
    """Проверка что публичные endpoints не получают auth headers"""
    print("\n" + "=" * 70)
    print("ТЕСТ 4: Проверка заголовков авторизации") 
    print("=" * 70)
    
    from exchange.base_client import BybitRestClient
    
    # Создаем клиент с API keys (как в боте)
    client = BybitRestClient(testnet=True)
    
    print(f"\nAPI Keyпrisent: {bool(client.api_key)}")
    print(f"API Key: {client.api_key[:20]}..." if client.api_key else "None")
    
    # Перехватываем запрос чтобы увидеть headers
    import unittest.mock as mock
    
    with mock.patch.object(client.session, 'get') as mock_get:
        # Мокируем успешный ответ
        mock_response = mock.Mock()
        mock_response.json.return_value = {"retCode": 0, "result": {}}
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response
        
        # Вызываем get с signed=False (как для kline)
        client.get("/v5/market/kline", params={"symbol": "BTCUSDT", "interval": "60"}, signed=False)
        
        # Проверяем какие headers были переданы
        call_args = mock_get.call_args
        headers_sent = call_args[1].get('headers', {}) if call_args else {}
        
        print(f"\nHeaders sent to session.get():")
        for k, v in headers_sent.items():
            if k.startswith("X-BAPI"):
                print(f"  ⚠️  {k}: {v[:20]}..." if len(str(v)) > 20 else f"  ⚠️  {k}: {v}")
            else:
                print(f"  {k}: {v}")
        
        if any(k.startswith("X-BAPI") for k in headers_sent.keys()):
            print("\n❌ ПРОБЛЕМА: Auth заголовки присутствуют для публичного endpoint!")
        else:
            print("\n✅ OK: Auth заголовки отсутствуют")


if __name__ == "__main__":
    test_kline_direct()
    test_all_symbols()
    test_kline_with_our_client()
    check_authentication_headers()
    
    print("\n" + "=" * 70)
    print("Диагностика завершена")
    print("=" * 70)
