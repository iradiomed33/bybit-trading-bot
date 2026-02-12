"""
Диагностика проблем с Bybit V5 API после исправления авторизации.

Проверяет:
1. Leverage settings
2. Kline interval format  
3. Instruments-info на testnet
4. Символы на валидность
"""

import os
import sys
import requests
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from config import Config

print("=" * 70)
print("ДИАГНОСТИКА BYBIT V5 API")
print("=" * 70)

# Тест 1: Проверка конфигурации leverage
print("\n📋 Тест 1: Проверка max_leverage в конфигах")

configs = [
    "config/bot_settings_AGGRESSIVE_TESTNET.json",
    "config/bot_settings_PRODUCTION.json",
]

for config_path in configs:
    if Path(config_path).exists():
        import json
        with open(config_path) as f:
            data = json.load(f)
            lev = data.get("risk_management", {}).get("max_leverage", "NOT SET")
            print(f"  {config_path}: max_leverage = {lev}")
            if isinstance(lev, (int, float)) and lev > 75:
                print(f"    ⚠️  WARNING: {lev}x может превышать testnet лимит (обычно 50-75x)")
            elif isinstance(lev, (int, float)) and lev <= 50:
                print(f"    ✅ OK: {lev}x безопасно для testnet")
    else:
        print(f"  {config_path}: NOT FOUND")

# Тест 2: Проверка kline на testnet (без auth)
print("\n📋 Тест 2: Проверка /v5/market/kline на testnet")

testnet_url = "https://api-testnet.bybit.com"
symbols_to_test = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

for symbol in symbols_to_test:
    url = f"{testnet_url}/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "60",  # 1 час
        "limit": 10,
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        ret_code = data.get("retCode", -1)
        ret_msg = data.get("retMsg", "Unknown")
        
        if ret_code == 0:
            candles = data.get("result", {}).get("list", [])
            print(f"  {symbol}: ✅ OK ({len(candles)} candles)")
        else:
            print(f"  {symbol}: ❌ ERROR retCode={ret_code}, msg={ret_msg}")
            if ret_code == 10001:
                print(f"    → Symbol invalid or testnet doesn't support it")
                
    except Exception as e:
        print(f"  {symbol}: ❌ REQUEST FAILED: {e}")

# Тест 3: Проверка instruments-info на testnet (без auth)
print("\n📋 Тест 3: Проверка /v5/market/instruments-info на testnet")

url = f"{testnet_url}/v5/market/instruments-info"
params = {
    "category": "linear",
    "limit": 10,
}

try:
    response = requests.get(url, params=params, timeout=5)
    data = response.json()
    ret_code = data.get("retCode", -1)
    ret_msg = data.get("retMsg", "Unknown")
    
    if ret_code == 0:
        instruments = data.get("result", {}).get("list", [])
        print(f"  ✅ OK: {len(instruments)} instruments loaded")
        if len(instruments) > 0:
            first = instruments[0]
            print(f"  Example: {first.get('symbol')} - tick={first.get('priceScale')}, qty={first.get('qtyScale')}")
    else:
        print(f"  ❌ ERROR retCode={ret_code}, msg={ret_msg}")
        if ret_code == 10001 and "Illegal category" in ret_msg:
            print(f"  → Testnet instruments-info не работает (известная проблема)")
            print(f"  → Бот использует fallback DEFAULT_INSTRUMENT_PARAMS")
            
except Exception as e:
    print(f"  ❌ REQUEST FAILED: {e}")

# Тест 4: Проверка формата interval
print("\n📋 Тест 4: Валидация kline interval")

valid_intervals = ["1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"]
test_intervals = ["60", 60, "1h", "daily"]

for interval in test_intervals:
    interval_str = str(interval)
    if interval_str in valid_intervals:
        print(f"  {repr(interval)} → {repr(interval_str)}: ✅ VALID")
    else:
        print(f"  {repr(interval)} → {repr(interval_str)}: ❌ INVALID (should be one of {valid_intervals})")

# Итоговая сводка
print("\n" + "=" * 70)
print("РЕКОМЕНДАЦИИ")
print("=" * 70)

print("""
1. Leverage Issues (retCode=110013):
   - Понизьте max_leverage в конфиге до 10-50 для testnet
   - Бот теперь автоматически ограничивает leverage до 50x на testnet
   
2. Kline Invalid Symbol (retCode=10001):
   - Если testnet отклоняет все символы, попробуйте interval="1" (1 минута)
   - Или используйте mainnet для публичных данных (kline не требует auth)
   
3. Instruments-info Failed:
   - Бот теперь использует fallback DEFAULT_INSTRUMENT_PARAMS
   - Поддерживаются: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT
   
4. Next Steps:
   - Перезапустите бота и проверьте логи
   - Ищите "[CONFIG] ✓ set_leverage success" (должен быть <=50x)
   - Проверьте что kline работает хотя бы для одного символа
""")

print("=" * 70)
