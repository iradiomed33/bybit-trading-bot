#!/usr/bin/env python3
"""
Быстрый тест что бот может загрузить данные для всех символов
"""
from exchange.market_data import MarketDataClient
from exchange.account import AccountClient
from config import Config


def quick_test():
    print("=" * 70)
    print("БЫСТРЫЙ ТЕСТ БОТА")
    print("=" * 70)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    
    # Тест 1: Публичные данные (kline)
    print("\n1. Тест публичных endpoints (kline)")
    print("-" * 70)
    
    market_client = MarketDataClient(testnet=True)
    
    for symbol in symbols:
        try:
            response = market_client.get_kline(symbol=symbol, interval="60", limit=5)
            
            if response.get("retCode") == 0:
                candles = len(response.get("result", {}).get("list", []))
                print(f"  {symbol}: ✅ OK ({candles} свечей)")
            else:
                print(f"  {symbol}: ❌ {response.get('retMsg')}")
        except Exception as e:
            print(f"  {symbol}: ❌ {str(e)[:50]}")
    
    # Тест 2: Приватные endpoints
    print("\n2. Тест приватных endpoints")
    print("-" * 70)
    
    account_client = AccountClient(testnet=True)
    
    # Баланс
    try:
        response = account_client.get_wallet_balance()
        if response.get("retCode") == 0:
            print(f"  Баланс: ✅ OK")
        else:
            print(f"  Баланс: ❌ {response.get('retMsg')}")
    except Exception as e:
        print(f"  Баланс: ❌ {str(e)[:50]}")
    
    # Позиции
    try:
        response = account_client.get_positions(category="linear")
        if response.get("retCode") == 0:
            positions = len(response.get("result", {}).get("list", []))
            print(f"  Позиции: ✅ OK ({positions} позиций)")
        else:
            print(f"  Позиции: ❌ {response.get('retMsg')}")
    except Exception as e:
        print(f"  Позиции: ❌ {str(e)[:50]}")
    
    # Открытые ордера
    try:
        response = account_client.get_open_orders(category="linear")
        if response.get("retCode") == 0:
            orders = len(response.get("result", {}).get("list", []))
            print(f"  Ордера: ✅ OK ({orders} открытых)")
        else:
            print(f"  Ордера: ❌ {response.get('retMsg')}")
    except Exception as e:
        print(f"  Ордера: ❌ {str(e)[:50]}")
    
    print("\n" + "=" * 70)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 70)
    print("\n✅ Если все тесты прошли успешно, бот готов к запуску!")
    print("   Используйте: python cli.py live --symbols BTCUSDT ETHUSDT\n")


if __name__ == "__main__":
    quick_test()
