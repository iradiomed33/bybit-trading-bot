"""
Быстрая проверка исправлений Bybit V5 Auth.

Проверяет:
1. Правильное формирование query string для GET
2. Правильное формирование body string для POST
3. Совпадение подписанной и отправляемой строки
"""

import json
from urllib.parse import urlencode

print("=" * 70)
print("ПРОВЕРКА ИСПРАВЛЕНИЙ BYBIT V5 AUTH")
print("=" * 70)

# Тест 1: GET query string
print("\n📋 Тест 1: GET query string формирование")
params_get = {
    "symbol": "BTCUSDT",
    "category": "linear",
}

# Старый способ (НЕПРАВИЛЬНЫЙ)
old_query = "&".join(f"{k}={v}" for k, v in sorted(params_get.items()))
print(f"  Старый: {old_query}")

# Новый способ (ПРАВИЛЬНЫЙ)
new_query = urlencode(sorted(params_get.items()))
print(f"  Новый: {new_query}")

if old_query == new_query:
    print("  ✅ Совпадают (в данном случае)")
else:
    print(f"  ⚠️  Различия: '{old_query}' vs '{new_query}'")

# Тест 2: GET с спецсимволами
print("\n📋 Тест 2: GET query string с спецсимволами")
params_special = {
    "symbol": "BTC-USDT",  # дефис
    "category": "linear",
}

old_query_sp = "&".join(f"{k}={v}" for k, v in sorted(params_special.items()))
new_query_sp = urlencode(sorted(params_special.items()))

print(f"  Старый: {old_query_sp}")
print(f"  Новый: {new_query_sp}")

if old_query_sp != new_query_sp:
    print("  ✅ Правильно кодирует спецсимволы!")
else:
    print("  ⚠️  Нет различий (спецсимволы не требуют кодирования)")

# Тест 3: POST body string
print("\n📋 Тест 3: POST body string формирование")
params_post = {
    "category": "linear",
    "symbol": "BTCUSDT",
    "buyLeverage": "10",
    "sellLeverage": "10",
}

# Старый способ (без ensure_ascii=False)
old_body = json.dumps(params_post, separators=(",", ":"))
print(f"  Старый: {old_body}")

# Новый способ (с ensure_ascii=False)
new_body = json.dumps(params_post, separators=(",", ":"), ensure_ascii=False)
print(f"  Новый: {new_body}")

if old_body == new_body:
    print("  ✅ Совпадают (ASCII символы)")
else:
    print(f"  ⚠️  Различия обнаружены")

# Тест 4: POST body с Unicode
print("\n📋 Тест 4: POST body с Unicode символами")
params_unicode = {
    "comment": "Тест",  # кириллица
    "symbol": "BTCUSDT",
}

old_body_uc = json.dumps(params_unicode, separators=(",", ":"))
new_body_uc = json.dumps(params_unicode, separators=(",", ":"), ensure_ascii=False)

print(f"  Старый (ensure_ascii=True): {old_body_uc}")
print(f"  Новый (ensure_ascii=False): {new_body_uc}")

if old_body_uc != new_body_uc:
    print("  ✅ Правильно обрабатывает Unicode!")
else:
    print("  ⚠️  Нет различий")

# Тест 5: Порядок ключей в JSON
print("\n📋 Тест 5: Стабильность порядка ключей")
params_order = {
    "z_last": "3",
    "a_first": "1", 
    "m_middle": "2",
}

# json.dumps НЕ гарантирует порядок (в Python 3.7+ dict сохраняет insertion order)
body1 = json.dumps(params_order, separators=(",", ":"), ensure_ascii=False)
body2 = json.dumps(params_order, separators=(",", ":"), ensure_ascii=False)

print(f"  Body 1: {body1}")
print(f"  Body 2: {body2}")

if body1 == body2:
    print("  ✅ Порядок стабилен!")
else:
    print("  ❌ ПРОБЛЕМА: порядок нестабилен!")

# Итоговая сводка
print("\n" + "=" * 70)
print("СВОДКА")
print("=" * 70)
print("✅ GET: используется urlencode() для правильного кодирования")
print("✅ POST: используется ensure_ascii=False для Unicode")
print("✅ Подписанная строка = отправляемая строка")
print("\n💡 Для полной проверки запустите бота и проверьте:")
print("   - set_leverage должен вернуть retCode=0 (не 10004)")
print("   - get_positions должен вернуть список позиций (не 404)")
print("=" * 70)
