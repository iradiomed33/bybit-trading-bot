# Унификация контракта результатов API (OrderResult)

## Проблема

До этого изменения разные части кода проверяли результаты API операций по-разному:
- Низкоуровневые вызовы проверяли `response.get("retCode") == 0`
- Высокоуровневые методы возвращали `{"success": bool, "order_id": str, "error": str}`

Это приводило к:
- **Несогласованности кода**: разные стили проверки в разных местах
- **"Невидимым" ордерам**: логика не всегда правильно обрабатывала успешные результаты
- **Сложности поддержки**: нужно помнить, где какой формат используется

## Решение

Введена **единая структура** `OrderResult` для всех операций с ордерами:

```python
@dataclass
class OrderResult:
    success: bool                        # Успешна ли операция
    order_id: Optional[str] = None      # ID созданного/обновлённого ордера
    error: Optional[str] = None         # Сообщение об ошибке
    raw: Dict[str, Any] = field(...)    # Сырой ответ API
```

### Преимущества

1. **Единообразие**: везде используется одна структура
2. **Безопасность типов**: IDE может подсказывать доступные поля
3. **Удобство**: можно использовать в условиях напрямую: `if result: ...`
4. **Обратная совместимость**: метод `to_dict()` для старого кода
5. **Доступ к сырым данным**: поле `raw` для дополнительной информации

## Изменённые файлы

### 1. execution/order_result.py (новый)
**Класс OrderResult** с методами:
- `from_api_response(response)` - парсинг ответа Bybit API
- `success_result(order_id, raw)` - создание успешного результата
- `error_result(error, raw)` - создание результата с ошибкой
- `to_dict()` - конвертация в словарь (обратная совместимость)
- `__bool__()` - использование в условиях

### 2. execution/order_manager.py
**Обновлены методы:**
- `create_order()` → возвращает `OrderResult`
- `cancel_order()` → возвращает `OrderResult`
- `cancel_all_orders()` → возвращает `OrderResult`

**Было:**
```python
if response.get("retCode") == 0:
    order_id = response.get("result", {}).get("orderId")
    return {"success": True, "order_id": order_id}
else:
    return {"success": False, "error": response.get("retMsg")}
```

**Стало:**
```python
result = OrderResult.from_api_response(response)
if result.success:
    logger.info(f"✓ Order created: {result.order_id}")
    # ...
return result
```

### 3. execution/stop_loss_tp_manager.py
**Обновлена обработка результатов** create_order():

**Было:**
```python
if sl_result.get("retCode") != 0:
    logger.warning(f"Failed: {sl_result.get('retMsg')}")
    sl_order_id = None
else:
    sl_order_id = sl_result.get("result", {}).get("orderId")
```

**Стало:**
```python
if not sl_result.success:
    logger.warning(f"Failed: {sl_result.error}")
    sl_order_id = None
else:
    sl_order_id = sl_result.order_id
```

### 4. bot/trading_bot.py
**Обновлён** `_process_signal()`:

**Было:**
```python
if order_result.get("retCode") == 0:
    order_id = order_result.get("result", {}).get("orderId")
    # ...
else:
    logger.error(f"Failed: {order_result}")
```

**Стало:**
```python
if order_result.success:
    order_id = order_result.order_id
    # ...
else:
    logger.error(f"Failed: {order_result.error}")
```

### 5. execution/__init__.py
Добавлен экспорт `OrderResult` для удобного импорта:
```python
from execution import OrderResult
```

## Примеры использования

### Создание ордера
```python
from execution import OrderManager, OrderResult

order_manager = OrderManager(client, db)
result = order_manager.create_order(
    category="linear",
    symbol="BTCUSDT",
    side="Buy",
    order_type="Market",
    qty=0.01
)

# Проверка результата
if result.success:
    print(f"Order created: {result.order_id}")
else:
    print(f"Error: {result.error}")

# Или короче
if result:
    print(f"Success! Order: {result.order_id}")
```

### Обратная совместимость
```python
# Старый код ожидает dict
result = order_manager.create_order(...)
result_dict = result.to_dict()

# Теперь можно использовать как dict
if result_dict.get("success"):
    order_id = result_dict.get("order_id")
```

### Парсинг API ответа
```python
response = client.post("/v5/order/create", params=...)
result = OrderResult.from_api_response(response)

# Автоматически разбирает retCode, retMsg, orderId
print(result.success)  # True или False
print(result.order_id)  # ID ордера или None
print(result.error)     # Сообщение об ошибке или None
```

## Тестирование

Создан файл `test_order_result.py` с тестами:
- Парсинг успешных ответов API
- Парсинг ответов с ошибками
- Создание результатов через helper-методы
- Конвертация в dict
- Использование в условиях
- Обратная совместимость

**Запуск тестов:**
```bash
python test_order_result.py
```

## Миграция существующего кода

### Проверка результатов
**Было:**
```python
result = order_manager.create_order(...)
if result.get("success"):
    order_id = result.get("order_id")
```

**Стало:**
```python
result = order_manager.create_order(...)
if result.success:
    order_id = result.order_id
```

### Обработка ошибок
**Было:**
```python
if not result.get("success"):
    error = result.get("error", "Unknown error")
    logger.error(error)
```

**Стало:**
```python
if not result.success:
    logger.error(result.error)
```

## Совместимость

### Обратная совместимость
`OrderResult.to_dict()` возвращает словарь в старом формате, что позволяет постепенно мигрировать код.

### Прямые вызовы API
Проверки `retCode` для **market data** API (kline, orderbook и т.д.) **не изменены**, так как они не относятся к операциям с ордерами.

## Готово когда ✅

- [x] Любое место кода не проверяет retCode для **ордеров** напрямую
- [x] Используется success/order_id из OrderResult
- [x] Все методы OrderManager возвращают OrderResult
- [x] StopLossTakeProfitManager использует OrderResult
- [x] TradingBot._process_signal() использует OrderResult
- [x] Созданы тесты для OrderResult

## Статус

✅ **ГОТОВО** - Контракт результатов API унифицирован для всех операций с ордерами.
