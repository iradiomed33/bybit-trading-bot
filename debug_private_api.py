#!/usr/bin/env python3
"""
Диагностика приватных endpoints
"""
from config import Config
from exchange.account import AccountClient
import json


def test_position_list():
    """Тест get_positions"""
    print("=" * 70)
    print("ТЕСТ: get_positions (приватный endpoint)")
    print("=" * 70)
    
    client = AccountClient(testnet=True)
    
    print(f"\nAPI Key: {Config.BYBIT_API_KEY[:20]}...")
    print(f"Testnet: {client.client.base_url}")
    
    try:
        response = client.get_positions(category="linear", symbol="BTCUSDT")
        
        if response.get("retCode") == 0:
            print("\n✅ Успех!")
            positions = response.get("result", {}).get("list", [])
            print(f"Позиций: {len(positions)}")
            if positions:
                print(json.dumps(positions[0], indent=2))
        else:
            print(f"\n❌ Ошибка: {response.get('retCode')} - {response.get('retMsg')}")
            print(json.dumps(response, indent=2))
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()


def test_open_orders():
    """Тест get_open_orders"""
    print("\n" + "=" * 70)
    print("ТЕСТ: get_open_orders (приватный endpoint)")
    print("=" * 70)
    
    client = AccountClient(testnet=True)
    
    try:
        response = client.get_open_orders(category="linear", symbol="BTCUSDT")
        
        if response.get("retCode") == 0:
            print("\n✅ Успех!")
            orders = response.get("result", {}).get("list", [])
            print(f"Открытых ордеров: {len(orders)}")
        else:
            print(f"\n❌ Ошибка: {response.get('retCode')} - {response.get('retMsg')}")
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_wallet_balance():
    """Тест get_wallet_balance"""
    print("\n" + "=" * 70)
    print("ТЕСТ: get_wallet_balance (приватный endpoint)")
    print("=" * 70)
    
    client = AccountClient(testnet=True)
    
    try:
        response = client.get_wallet_balance(accountType="UNIFIED")
        
        if response.get("retCode") == 0:
            print("\n✅ Успех!")
            balance_list = response.get("result", {}).get("list", [])
            if balance_list:
                total_equity = balance_list[0].get("totalEquity", "0")
                print(f"Total Equity: {total_equity} USDT")
        else:
            print(f"\n❌ Ошибка: {response.get('retCode')} - {response.get('retMsg')}")
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")


if __name__ == "__main__":
    test_wallet_balance()  # Самый простой endpoint
    test_position_list()
    test_open_orders()
    
    print("\n" + "=" * 70)
    print("Диагностика завершена")
    print("=" * 70)
