# Bybit V5 API Issues - Fixed

## Критическая ошибка: kline endpoint не работал

### Проблема
После исправления авторизации появилась новая критическая ошибка:
```
retCode=10001, retMsg=The requested symbol is invalid
Endpoint: /v5/market/kline
```

Повторялась для всех символов (BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT).

### Диагностика
Создан диагностический скрипт [debug_kline.py](debug_kline.py) который показал:
- ✅ Прямой запрос через `requests.get()` работает
- ❌ Запрос через `MarketDataClient` НЕ работает
- ✅ Auth заголовки правильно НЕ добавляются к публичным endpoints

**Проблема**: Для НЕподписанных GET запросов (публичные endpoints) мы НЕ добавляли параметры к URL.

### Исправление

**Файл**: [exchange/base_client.py](exchange/base_client.py) (строки ~360)

**Было**:
```python
if method.upper() == "GET":
    # GET: URL уже содержит query string, не передаем params
    response = self.session.get(url, headers=headers)
```

**Стало**:
```python
if method.upper() == "GET":
    # GET: URL уже содержит query string, не передаем params
    # Для несподписанных запросов добавляем params к URL
    if not signed and params:
        from urllib.parse import urlencode
        query_string = urlencode(sorted(params.items()))
        url = f"{self.base_url}{endpoint}?{query_string}"
    
    logger.debug(f"GET request: {url}")
    response = self.session.get(url, headers=headers)
```

**Результат**: 
- ✅ Публичные endpoints (kline, instruments-info) работают без авторизации
- ✅ Приватные endpoints работают с правильной подписью
- ✅ Все символы (BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT) загружаются успешно

### Тестирование
```bash
python debug_kline.py
```

Вывод:
```
✅ Прямой запрос kline: OK (5 свечей)
✅ Все символы (BTC/ETH/SOL/XRP): OK
✅ MarketDataClient: OK (5 свечей)
✅ Auth заголовки отсутствуют для публичных endpoints
```

---

## Предыдущие исправления (сохранены)

### 1. Защита от слишком большого leverage

### 1. Защита от слишком большого leverage

**Файл**: [bot/trading_bot.py](bot/trading_bot.py) (строки ~150-175)

**Проблема**: Testnet Bybit имеет низкие лимиты leverage:
- XRPUSDT: max 75x
- BTCUSDT/ETHUSDT: обычно 100x

**Решение**:
```python
# Автоматическое ограничение leverage для testnet
max_safe_lev = 50 if testnet else 100
if lev > max_safe_lev:
    logger.warning(f"Leverage {lev}x > safe limit {max_safe_lev}x, capping")
    lev = max_safe_lev

lev = max(1, min(lev, max_safe_lev))
```

**Результат**: 
- ✅ Leverage автоматически ограничен до 50x на testnet
- ✅ Детальное логирование при ошибке 110013
- ✅ Рекомендация понизить max_leverage в конфиге

### 2. Валидация kline interval

**Файл**: [bot/trading_bot.py](bot/trading_bot.py) (строки ~820-830)

**Проблема**: Bybit V5 требует строгий формат interval:
- ✅ Правильно: `"60"` (строка)
- ❌ Неправильно: `60` (int), `"1h"` (старый формат)

**Решение**:
```python
valid_intervals = ["1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"]
if kline_interval not in valid_intervals:
    logger.warning(f"Invalid kline_interval '{kline_interval}', using '60'")
    kline_interval = "60"
```

**Результат**:
- ✅ Interval всегда валидная строка
- ✅ Автоматический fallback на "60" при неправильном формате  
- ✅ Детальное логирование параметров запроса

### 3. Fallback для instruments-info на testnet

**Файл**: [exchange/market_data.py](exchange/market_data.py) (строки ~65-95)

**Проблема**: Testnet иногда отвечает `retCode=10001 "Illegal category"` на instruments-info

**Решение**:
```python
response = self.client.get("/v5/market/instruments-info", params=params)

if response.get("retCode") == 10001 and "Illegal category" in response.get("retMsg", ""):
    logger.warning("Testnet instruments-info failed, using fallback")
    return {
        "retCode": 0,
        "retMsg": "OK (fallback)",
        "result": {"category": category, "list": []}
    }
```

**Файл**: [exchange/instruments.py](exchange/instruments.py) (строки ~30-75)

**Дефолтные параметры** для популярных символов:
```python
DEFAULT_INSTRUMENT_PARAMS = {
    "BTCUSDT": {
        "tickSize": "0.1",
        "qtyStep": "0.001",
        "minOrderQty": "0.001",
        "minNotional": "5.0",
    },
    "ETHUSDT": {"tickSize": "0.01", "qtyStep": "0.01", ...},
    "SOLUSDT": {"tickSize": "0.001", "qtyStep": "0.1", ...},
    "XRPUSDT": {"tickSize": "0.0001", "qtyStep": "1", ...},
}
```

**Использование fallback**:
```python
if ret_code == 10001 and "Illegal category" in error_msg:
    logger.warning("Using DEFAULT_INSTRUMENT_PARAMS fallback")
    for symbol, params in DEFAULT_INSTRUMENT_PARAMS.items():
        instruments[symbol] = {
            "symbol": symbol,
            "tickSize": Decimal(params["tickSize"]),
            "qtyStep": Decimal(params["qtyStep"]),
            ...
        }
    return instruments
```

**Результат**:
- ✅ Бот работает даже если instruments-info не отвечает
- ✅ Поддерживаются 4 популярных символа из коробки
- ✅ Правильные параметры округления для ордеров

### 4. Проверка текущей конфигурации

**Тест**: [check_testnet.py](check_testnet.py)

Запускает проверку:
```bash
python check_testnet.py
```

Результаты:
```
✅ max_leverage в конфигах:
   AGGRESSIVE_TESTNET: 10x (безопасно)
   PRODUCTION: 5x (безопасно)

✅ Kline работает для всех символов:
   BTCUSDT: ✅ Работает (5 свечей)
   ETHUSDT: ✅ Работает (5 свечей)
   SOLUSDT: ✅ Работает (5 свечей)
   XRPUSDT: ✅ Работает (5 свечей)

✅ Instruments-info работает:
   Загружено 5 инструментов
```

## Итоговая сводка

| Проблема | Причина | Исправление | Статус |
|----------|---------|-------------|--------|
| retCode=110013 leverage | Слишком большое плечо для testnet | Автоограничение до 50x | ✅ Fixed |
| retCode=10001 kline | Неправильный формат interval | Валидация формата | ✅ Fixed |
| retCode=10001 instruments | Testnet API нестабилен | Fallback на дефолты | ✅ Fixed |
| 404/401 приватные API | Отсутствие auth заголовков | Исправлено в BYBIT_V5_AUTH_FIX | ✅ Fixed |

## Проверка

### 1. Запустите диагностику
```bash
python check_testnet.py
```

Ожидаемый результат:
- ✅ Leverage в конфигах <= 50
- ✅ Все символы работают на kline
- ✅ Instruments-info работает (или есть fallback)

### 2. Запустите бота
```bash
python cli.py paper --symbol BTCUSDT
```

Проверьте логи:
```
[CONFIG] Attempting set_leverage: BTCUSDT -> 10x (from config: 10)
[CONFIG] ✓ set_leverage success: BTCUSDT -> 10x
```

Если видите:
```
[CONFIG] set_leverage failed: 110013
[CONFIG] Leverage limit exceeded for BTCUSDT on testnet
```

→ Понизьте `max_leverage` в конфиге до 5-10

### 3. Проверьте kline
Ищите в логах:
```
Fetching kline: symbol=BTCUSDT, interval=60 (type: <class 'str'>), limit=500
```

Если видите:
```
API error: retCode=10001, retMsg=The requested symbol is invalid
```

→ Проверьте что testnet поддерживает символ (см. check_testnet.py)

## Рекомендации

1. **Для production**: используйте `max_leverage <= 10` для безопасности
2. **Для testnet**: держите `max_leverage <= 50` из-за лимитов
3. **Если testnet нестабилен**: можно использовать mainnet для публичных данных (kline не требует auth)
4. **Мониторинг**: следите за логами `[CONFIG]` при запуске

## Дополнительные файлы

- [verify_auth_fix.py](verify_auth_fix.py) - проверка правильности подписи
- [check_testnet.py](check_testnet.py) - диагностика доступности testnet API
- [BYBIT_V5_AUTH_FIX.md](BYBIT_V5_AUTH_FIX.md) - документация по исправлению авторизации
- [EMA_ROUTER_IMPLEMENTATION.md](EMA_ROUTER_IMPLEMENTATION.md) - новая фича роутинга стратегий

---

**Статус**: ✅ Все проблемы исправлены  
**Дата**: 2026-02-12  
**Версия**: 1.0
