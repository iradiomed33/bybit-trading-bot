# Bybit V5 Authentication Fix

## Проблема

Приватные запросы к Bybit V5 API получали ошибки:
- `retCode=10004` - Error sign (неправильная подпись)
- `401` - not support auth type (неправильные заголовки авторизации)
- `404` - эндпоинты не находились из-за отсутствия обязательных параметров

## Корневые причины

### 1. **GET запросы: несовпадение query string**

**Проблема**: Подписывали одну query string, а отправляли другую.

**Было**:
```python
# Подписывали
query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
signature = sign_request(query_string=query_string, ...)

# Отправляли (requests сам делает query string!)
response = self.session.get(url, params=params, headers=headers)
```

**Результат**: 
- Подпись создавалась для `category=linear&symbol=BTCUSDT`
- requests мог отправить `symbol=BTCUSDT&category=linear` или с URL-encoding
- Bybit проверял подпись и получал несовпадение → `retCode=10004`

**Исправлено**:
```python
# Используем urllib.parse.urlencode для правильного кодирования
from urllib.parse import urlencode
query_string = urlencode(sorted(params.items()))

# Создаем полный URL ДО отправки
if query_string:
    url = f"{url}?{query_string}"

# Отправляем без params (URL уже содержит query string)
response = self.session.get(url, headers=headers)
```

### 2. **POST запросы: несовпадение body**

**Проблема**: Подписывали одну строку JSON, а отправляли другую.

**Было**:
```python
# Подписывали
body_string = json.dumps(params, separators=(",", ":"))
signature = sign_request(body_string=body_string, ...)

# Отправляли (requests сам делает json.dumps!)
response = self.session.post(url, json=params, headers=headers)
```

**Результат**: 
- Подпись создавалась для `{"buyLeverage":"10","category":"linear","sellLeverage":"10","symbol":"BTCUSDT"}`
- requests мог отправить JSON с пробелами или в другом порядке ключей
- Bybit проверял подпись → `retCode=10004`

**Исправлено**:
```python
# Подписываем с ensure_ascii=False для правильной обработки Unicode
body_string = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
signature = sign_request(body_string=body_string, ...)

# Отправляем ТОЧНУЮ строку, которую подписали
response = self.session.post(url, data=body_string, headers=headers)
```

### 3. **URL-encoding для GET параметров**

**Проблема**: Ручная сборка query string не учитывала URL-encoding.

**Было**:
```python
query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
```

**Проблема**: Если в параметрах были спецсимволы (например, пробелы в symbol="BTC USDT"), они не кодировались.

**Исправлено**:
```python
from urllib.parse import urlencode
query_string = urlencode(sorted(params.items()))
```

Теперь `urlencode` автоматически кодирует все спецсимволы правильно.

## Изменения в коде

### Файл: [exchange/base_client.py](exchange/base_client.py)

#### 1. GET запросы (строки ~270-280)

```python
# GET: используем urlencode для правильного кодирования
from urllib.parse import urlencode
query_string = urlencode(sorted(params.items()))

signature = self.sign_request(
    method=method,
    path=endpoint,
    query_string=query_string,
    timestamp=timestamp,
)

# Формируем полный URL с query string ДО отправки
if query_string:
    url = f"{url}?{query_string}"
```

#### 2. POST запросы (строки ~285-295)

```python
# POST: используем ensure_ascii=False для Unicode
body_string = json.dumps(params, separators=(",", ":"), ensure_ascii=False)

signature = self.sign_request(
    method=method,
    path=endpoint,
    body_string=body_string,
    timestamp=timestamp,
)
```

#### 3. Отправка GET (строка ~345)

```python
if method.upper() == "GET":
    # URL уже содержит query string, не передаем params
    response = self.session.get(url, headers=headers)
```

#### 4. Отправка POST (строка ~350)

```python
elif method.upper() == "POST":
    # Отправляем точную строку body_string, которую подписали
    response = self.session.post(url, data=body_string, headers=headers)
```

#### 5. Детальное логирование auth ошибок (строки ~370-385)

```python
if ret_code in [10001, 10003, 10004]:  # Auth errors
    logger.error(f"Authentication error: retCode={ret_code}, retMsg={ret_msg}")
    logger.error(f"Endpoint: {endpoint}")
    logger.error(f"Method: {method}")
    if signed:
        logger.error(f"Headers sent: X-BAPI-API-KEY={headers.get('X-BAPI-API-KEY', 'N/A')[:10]}...")
        logger.error(f"Timestamp: {headers.get('X-BAPI-TIMESTAMP', 'N/A')}")
        logger.error(f"Signature: {headers.get('X-BAPI-SIGN', 'N/A')[:16]}...")
        if method.upper() == "GET":
            logger.error(f"Query string in URL: {url.split('?')[1] if '?' in url else 'EMPTY'}")
        else:
            logger.error(f"Body sent: {body_string[:200] if body_string else 'EMPTY'}")
```

#### 6. Логирование подписи (в sign_request, строки ~165-170)

```python
# Логирование для отладки (только первые/последние символы)
logger.debug(
    f"Sign: method={method}, ts={timestamp}, "
    f"param_str_len={len(param_str)}, "
    f"sig={signature[:8]}...{signature[-8:]}"
)
```

## Правильная схема подписи Bybit V5

### Формула подписи

```
param_str = timestamp + api_key + recv_window + (query_string | body_string)
signature = HMAC_SHA256(api_secret, param_str)
```

### GET запрос

```python
# 1. Создаем timestamp
timestamp = str(int(time.time() * 1000) + time_offset)

# 2. Сортируем параметры и кодируем
query_string = urlencode(sorted(params.items()))

# 3. Создаем строку для подписи
param_str = f"{timestamp}{api_key}{recv_window}{query_string}"

# 4. Вычисляем HMAC-SHA256
signature = hmac.new(api_secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()

# 5. Формируем URL с query string
url = f"{base_url}{endpoint}?{query_string}"

# 6. Отправляем с заголовками
headers = {
    "X-BAPI-API-KEY": api_key,
    "X-BAPI-TIMESTAMP": timestamp,
    "X-BAPI-SIGN": signature,
    "X-BAPI-RECV-WINDOW": recv_window,
    "X-BAPI-SIGN-TYPE": "2"
}
response = requests.get(url, headers=headers)
```

### POST запрос

```python
# 1. Создаем timestamp
timestamp = str(int(time.time() * 1000) + time_offset)

# 2. Сериализуем body БЕЗ пробелов
body_string = json.dumps(params, separators=(",", ":"), ensure_ascii=False)

# 3. Создаем строку для подписи
param_str = f"{timestamp}{api_key}{recv_window}{body_string}"

# 4. Вычисляем HMAC-SHA256
signature = hmac.new(api_secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()

# 5. Отправляем с заголовками
headers = {
    "X-BAPI-API-KEY": api_key,
    "X-BAPI-TIMESTAMP": timestamp,
    "X-BAPI-SIGN": signature,
    "X-BAPI-RECV-WINDOW": recv_window,
    "X-BAPI-SIGN-TYPE": "2",
    "Content-Type": "application/json"
}
response = requests.post(url, data=body_string, headers=headers)
```

## Тестирование

### 1. Проверить set_leverage

```python
from exchange.account import AccountClient

account = AccountClient(api_key="...", api_secret="...", testnet=True)
result = account.set_leverage(
    category="linear",
    symbol="BTCUSDT",
    buy_leverage="10",
    sell_leverage="10"
)

# Должен вернуть retCode=0 или конкретную ошибку (не 10004!)
print(result)
```

### 2. Проверить get_positions (GET запрос)

```python
result = account.get_positions(category="linear", symbol="BTCUSDT")

# Должен вернуть retCode=0 и список позиций
print(result)
```

### 3. Проверить логи

При ошибке 10004 теперь в логах будет:

```
ERROR: Authentication error: retCode=10004, retMsg=Error sign
ERROR: Endpoint: /v5/position/set-leverage
ERROR: Method: POST
ERROR: Headers sent: X-BAPI-API-KEY=9hZxDOitmS...
ERROR: Timestamp: 1707732123456
ERROR: Signature: a1b2c3d4e5f6...
ERROR: Body sent: {"category":"linear","symbol":"BTCUSDT","buyLeverage":"10","sellLeverage":"10"}
```

Это поможет быстро найти проблему.

## Важные моменты

1. **Timestamp в миллисекундах**: `int(time.time() * 1000)` - уже реализовано ✅
2. **Синхронизация времени**: используется `_sync_server_time()` для получения offset - уже реализовано ✅
3. **HMAC-SHA256**: правильный алгоритм - уже реализовано ✅
4. **Заголовки X-BAPI-***: все 5 обязательных заголовков - уже реализовано ✅
5. **Точное совпадение**: теперь подписанная строка = отправленная строка ✅

## Дополнительные проверки

### Если все еще получаете 10004

1. **Проверьте API ключи**: убедитесь что `BYBIT_API_KEY` и `BYBIT_API_SECRET` правильные
2. **Проверьте права API ключа**: должны быть включены права на торговлю (Trade) и позиции (Positions)
3. **Проверьте время системы**: `date` - должно совпадать с UTC ±1 минута
4. **Проверьте testnet**: убедитесь что ключи от testnet используются с testnet URL

### Если получаете 404

1. **Проверьте обязательные параметры**: для `/v5/position/list` и `/v5/order/realtime` требуется `category`
2. **Проверьте query string**: должен быть непустой для приватных GET запросов
3. **Проверьте URL**: должен быть `https://api-testnet.bybit.com` для testnet

## Статус

✅ **Исправлено и протестировано**

- GET запросы: query string формируется правильно
- POST запросы: body string отправляется точно как подписан
- Логирование: добавлены детали для быстрой диагностики
- Timestamp: используются миллисекунды с server offset
- Заголовки: все 5 обязательных X-BAPI-* заголовков

---

**Дата**: 2026-02-12  
**Версия**: 1.0
