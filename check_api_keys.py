"""
Проверка API ключей Bybit Testnet

Этот скрипт проверяет что API ключи установлены правильно
и могут использоваться для доступа к Bybit testnet API.
"""

import os
import sys
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загружаем .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ .env файл загружен")
except ImportError:
    print("⚠ python-dotenv не установлен. Установите: pip install python-dotenv")
    print("Попытка использовать системные переменные окружения...")

from exchange.account import AccountClient

def check_api_keys():
    """Проверка API ключей"""
    print("\n" + "="*60)
    print("ПРОВЕРКА API КЛЮЧЕЙ BYBIT TESTNET")
    print("="*60 + "\n")
    
    # Проверяем наличие ключей
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    
    if not api_key:
        print("❌ BYBIT_API_KEY не установлен!")
        print("\nСоздайте .env файл в корне проекта:")
        print("  BYBIT_API_KEY=your_testnet_api_key")
        print("  BYBIT_API_SECRET=your_testnet_api_secret")
        print("\nПодробнее: см. SETUP_API_KEYS.md")
        return False
    
    if not api_secret:
        print("❌ BYBIT_API_SECRET не установлен!")
        print("\nСоздайте .env файл в корне проекта:")
        print("  BYBIT_API_KEY=your_testnet_api_key")
        print("  BYBIT_API_SECRET=your_testnet_api_secret")
        print("\nПодробнее: см. SETUP_API_KEYS.md")
        return False
    
    # Показываем маскированные ключи
    print(f"API Key:    {api_key[:8]}...{api_key[-4:]}")
    print(f"API Secret: {'*' * 20} (установлен)")
    print()
    
    # Проверяем подключение к API
    print("Проверка подключения к Bybit testnet API...")
    
    try:
        client = AccountClient(api_key=api_key, api_secret=api_secret, testnet=True)
        
        # Пробуем получить позиции
        print("Запрос позиций по BTCUSDT...")
        response = client.get_positions(symbol='BTCUSDT')
        
        if response.get('retCode') != 0:
            print(f"\n❌ Ошибка API: {response.get('retMsg')}")
            print(f"Код ошибки: {response.get('retCode')}")
            
            if response.get('retCode') == 10004:
                print("\n💡 Это ошибка аутентификации. Проверьте:")
                print("  1. API ключи скопированы правильно (без пробелов)")
                print("  2. Используются TESTNET ключи, не production")
                print("  3. API ключ активен и не истек")
                print("\nПолучить ключи: https://testnet.bybit.com/app/user/api-management")
            
            return False
        
        # Успех!
        print("\n" + "="*60)
        print("✅ API КЛЮЧИ РАБОТАЮТ!")
        print("="*60)
        
        # Показываем информацию о позициях
        positions = response.get('result', {}).get('list', [])
        print(f"\nПозиций найдено: {len(positions)}")
        
        if positions:
            for pos in positions:
                symbol = pos.get('symbol')
                size = pos.get('size', '0')
                side = pos.get('side', 'None')
                unrealized_pnl = pos.get('unrealisedPnl', '0')
                print(f"  • {symbol}: size={size} side={side} PnL={unrealized_pnl}")
        else:
            print("  (нет открытых позиций)")
        
        # Проверяем баланс
        print("\nПроверка баланса...")
        try:
            balance_response = client.get_wallet_balance(coin='USDT')
            if balance_response.get('retCode') == 0:
                wallet_list = balance_response.get('result', {}).get('list', [])
                if wallet_list:
                    for wallet in wallet_list:
                        for coin_info in wallet.get('coin', []):
                            if coin_info.get('coin') == 'USDT':
                                balance = float(coin_info.get('walletBalance', '0'))
                                available = float(coin_info.get('availableToWithdraw', '0'))
                                print(f"  Баланс USDT: {balance:.2f}")
                                print(f"  Доступно: {available:.2f}")
                                
                                # Проверка достаточности баланса
                                if balance < 100:
                                    print(f"\n⚠️  ВНИМАНИЕ: Баланс {balance:.2f} USDT может быть недостаточным!")
                                    print("  Пополните баланс через: https://testnet.bybit.com/app/user/assets")
        except Exception as e:
            print(f"  (не удалось получить баланс: {e})")
        
        print("\n✅ Вы можете запускать E2E тесты!")
        print("\nЗапуск тестов:")
        print("  Windows: .\\run_e2e_testnet.bat")
        print("  Linux:   ./run_e2e_testnet.sh")
        print("  Вручную: $env:RUN_TESTNET_E2E=\"1\"; pytest tests\\e2e\\test_full_trade_cycle_testnet.py -v")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка подключения: {e}")
        print("\nПроверьте:")
        print("  1. Интернет соединение")
        print("  2. API ключи установлены правильно")
        print("  3. Bybit testnet доступен")
        return False

if __name__ == '__main__':
    success = check_api_keys()
    sys.exit(0 if success else 1)
