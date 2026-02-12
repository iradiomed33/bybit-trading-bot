"""
Простая диагностика Bybit testnet без импортов бота.
"""

import requests
import json
from pathlib import Path

print("=" * 70)
print("ДИАГНОСТИКА BYBIT V5 TESTNET API")
print("=" * 70)

# Тест 1: Leverage в конфигах
print("\n📋 Тест 1: Проверка max_leverage в конфигах")

configs = {
    "AGGRESSIVE_TESTNET": "config/bot_settings_AGGRESSIVE_TESTNET.json",
    "PRODUCTION": "config/bot_settings_PRODUCTION.json",
}

for name, path in configs.items():
    if Path(path).exists():
        with open(path) as f:
            data = json.load(f)
            lev = data.get("risk_management", {}).get("max_leverage", "NOT SET")
            print(f"  {name}: max_leverage = {lev}")
            if isinstance(lev, (int, float)):
                if lev > 75:
                    print(f"    ⚠️  {lev}x может превышать testnet limit (обычно 50-75x)")
                elif lev <= 50:
                    print(f"    ✅ {lev}x безопасно для testnet")
    else:
        print(f"  {name}: файл не найден")

# Тест 2: Kline на testnet
print("\n📋 Тест 2: Проверка kline для популярных символов")

testnet_url = "https://api-testnet.bybit.com"
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

for symbol in symbols:
    try:
        response = requests.get(
            f"{testnet_url}/v5/market/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": "60",
                "limit": 5,
            },
            timeout=5
        )
        data = response.json()
        
        if data.get("retCode") == 0:
            candles = data.get("result", {}).get("list", [])
            print(f"  {symbol}: ✅ Работает ({len(candles)} свечей)")
        else:
            print(f"  {symbol}: ❌ retCode={data.get('retCode')}, msg={data.get('retMsg', 'N/A')}")
    except Exception as e:
        print(f"  {symbol}: ❌ Ошибка запроса: {e}")

# Тест 3: Instruments-info
print("\n📋 Тест 3: Проверка instruments-info")

try:
    response = requests.get(
        f"{testnet_url}/v5/market/instruments-info",
        params={
            "category": "linear",
            "limit": 5,
        },
        timeout=5
    )
    data = response.json()
    
    if data.get("retCode") == 0:
        instruments = data.get("result", {}).get("list", [])
        print(f"  ✅ Работает ({len(instruments)} инструментов)")
        if instruments:
            print(f"  Пример: {instruments[0].get('symbol')}")
    else:
        print(f"  ❌ retCode={data.get('retCode')}, msg={data.get('retMsg', 'N/A')}")
        if "Illegal category" in data.get('retMsg', ''):
            print(f"  → Testnet instruments-info глючит (используем fallback)")
except Exception as e:
    print(f"  ❌ Ошибка запроса: {e}")

# Сводка
print("\n" + "=" * 70)
print("РЕКОМЕНДАЦИИ")
print("=" * 70)
print("""
✅ Исправления применены:
   1. Leverage автоматически ограничен до 50x на testnet
   2. Kline interval валидируется (только "60", не 60 или "1h")
   3. Instruments-info имеет fallback на дефолтные параметры
   
⚠️  Если получаете ошибки:
   1. retCode=110013 (leverage limit) → уменьшите max_leverage до 10
   2. retCode=10001 на kline → testnet может быть нестабилен
   3. retCode=10001 на instruments → уже есть fallback, должно работать
   
💡 Перезапустите бота и проверьте логи:
   - Ищите "[CONFIG] ✓ set_leverage success"
   - Проверьте что хотя бы один символ работает
""")
print("=" * 70)
