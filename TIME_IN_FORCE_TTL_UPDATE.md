# Time in Force & TTL Update

## Проблема

При внедрении Order Monitoring была обнаружена логическая несогласованность:

- **IOC (Immediate or Cancel)** и **FOK (Fill or Kill)** ордера обрабатываются биржей **мгновенно** (либо исполняются, либо отменяются)
- Но в коде **все Limit ордера** добавлялись в `pending_orders` с TTL=300s
- TTL для IOC/FOK **не имеет смысла** — биржа сама их обрабатывает немедленно

## Решение

### 1. Логика TTL в зависимости от Time in Force

**Обновлен:** [bot/trading_bot.py](bot/trading_bot.py#L2236-L2270)

```python
# IOC/FOK ордера не нуждаются в TTL - биржа их обработает мгновенно
apply_ttl = time_in_force not in ["IOC", "FOK"]

self.order_manager.pending_orders[order_id] = {
    ...
    "ttl_seconds": ttl if apply_ttl else None,
    "time_in_force": time_in_force,
    ...
}
```

**Результат:**
- **GTC** ордера: `ttl_seconds = 300` (или значение из конфига)
- **PostOnly** ордера: `ttl_seconds = 300` (работают как GTC)
- **IOC** ордера: `ttl_seconds = None` (биржа обработает)
- **FOK** ордера: `ttl_seconds = None` (биржа обработает)

### 2. Обновлен мониторинг pending ордеров

**Обновлен:** [execution/order_manager.py](execution/order_manager.py#L689-L695)

```python
# Проверяем TTL (time to live)
# IOC/FOK ордера могут не иметь TTL (биржа сама их отменяет)
ttl = pending_info.get("ttl_seconds")
time_elapsed = time.time() - pending_info["created_at"]
time_in_force = pending_info.get("time_in_force", "GTC")

...

elif order_status == "New" and ttl and time_elapsed > ttl:
    # Ордер не исполнился за TTL — отменяем (только для GTC/PostOnly)
```

**Проверка TTL:** только если `ttl` не None (т.е. только для GTC/PostOnly)

### 3. Добавлена настройка TTL в UI

**Обновлен:** [static/index.html](static/index.html#L309-L334)

**Новое поле:**
```html
<label class="form-label">
    TTL для Limit ордеров (секунды)
    <i class="bi bi-question-circle text-muted" data-bs-toggle="tooltip" 
       title="Time To Live - автоматическая отмена неисполненных лимитных ордеров. 
              Применяется только к GTC и PostOnly. IOC/FOK обрабатываются биржей мгновенно">
    </i>
</label>
<input type="number" class="form-control" id="settingTtlSeconds" 
       min="30" max="86400" step="30" value="300">
<small class="form-text text-muted">300 сек = 5 минут, 3600 сек = 1 час</small>
```

**Диапазон:** 30 секунд - 24 часа (86400 секунд)  
**По умолчанию:** 300 секунд (5 минут)

### 4. Обновлены tooltips

**Time in Force:**
```
GTC = ордер активен пока не исполнен или отменен (используется TTL)
IOC = исполнить немедленно или отменить (TTL не применяется)
FOK = исполнить полностью или отменить (TTL не применяется)
```

**Post-only:**
```
Ордер будет добавлен в стакан как maker (получаешь rebate). 
Если исполнится как taker, будет отменен. Работает как GTC с TTL
```

**TTL:**
```
Time To Live - автоматическая отмена неисполненных лимитных ордеров. 
Применяется только к GTC и PostOnly. IOC/FOK обрабатываются биржей мгновенно
```

---

## Сравнение поведения

| Time in Force | TTL применяется? | Поведение |
|---------------|------------------|-----------|
| **GTC** | ✅ Да | Ордер висит в стакане. Если не исполнился за TTL → отменяется ботом |
| **PostOnly** | ✅ Да | Работает как GTC. Если не исполнился за TTL → отменяется ботом |
| **IOC** | ❌ Нет | Биржа исполняет немедленно или отменяет. Бот только мониторит результат |
| **FOK** | ❌ Нет | Биржа исполняет полностью или отменяет. Бот только мониторит результат |

---

## Логи

### GTC/PostOnly с TTL:
```
[LIMIT ORDER] Added to pending: 123456 (Long 0.001 @ 65000), 
              TIF=GTC, TTL=300s. Position will be registered when filled.

# После 300s если не исполнился:
Order 123456 expired (TTL=300s), cancelling...
Expired orders (TTL): 1
```

### IOC/FOK без TTL:
```
[LIMIT ORDER] Added to pending: 123456 (Long 0.001 @ 65000), 
              TIF=IOC (no TTL - exchange will handle). Position will be registered when filled.

# Биржа отменяет мгновенно если не исполнился:
Order 123456 Cancelled
Cancelled orders: 1
```

---

## Настройки в UI

**Путь:** Dashboard → Settings → Execution Settings

1. **Тип ордера**: Market / Limit
2. **Time in Force**: GTC / IOC / FOK _(теперь с пояснением о TTL)_
3. **Post-only**: чекбокс _(теперь указано что работает как GTC)_
4. **TTL для Limit ордеров**: 30-86400 сек _(новое поле!)_

**Сохранение:** через кнопку "Сохранить настройки" → API `/api/config/update` → `bot_settings.json`

---

## Конфигурация

**bot_settings.json:**
```json
{
  "execution": {
    "order_type": "limit",
    "time_in_force": "GTC",
    "post_only": false,
    "ttl_seconds": 300
  }
}
```

**Примеры:**
- **Агрессивный:** `ttl_seconds: 60` (1 минута)
- **Стандартный:** `ttl_seconds: 300` (5 минут)
- **Консервативный:** `ttl_seconds: 1800` (30 минут)
- **Долгосрочный:** `ttl_seconds: 3600` (1 час)

---

## Техническая реализация

### 1. trading_bot.py (Order Placement)

```python
# Определяем нужно ли применять TTL
time_in_force = str(self.config.get("execution.time_in_force", "GTC") or "GTC")
apply_ttl = time_in_force not in ["IOC", "FOK"]

# Сохраняем в pending_orders
self.order_manager.pending_orders[order_id] = {
    "ttl_seconds": ttl if apply_ttl else None,  # None для IOC/FOK
    "time_in_force": time_in_force,             # Сохраняем для логов
    ...
}

# Логируем с указанием TIF
if apply_ttl:
    logger.info(f"[LIMIT ORDER] ... TIF={time_in_force}, TTL={ttl}s")
else:
    logger.info(f"[LIMIT ORDER] ... TIF={time_in_force} (no TTL - exchange will handle)")
```

### 2. order_manager.py (Monitoring)

```python
def monitor_pending_orders(self, position_callback=None):
    for order_id in order_ids:
        pending_info = self.pending_orders[order_id]
        
        # Получаем TTL и TIF
        ttl = pending_info.get("ttl_seconds")  # None для IOC/FOK
        time_in_force = pending_info.get("time_in_force", "GTC")
        
        ...
        
        # Проверяем TTL только если он определен
        elif order_status == "New" and ttl and time_elapsed > ttl:
            logger.warning(f"Order {order_id} expired (TTL={ttl}s), cancelling...")
            cancel_result = self.cancel_order("linear", symbol, order_id=order_id)
```

**Ключевое изменение:** `and ttl` — проверка TTL только если он не None

### 3. app.js (UI Integration)

```javascript
// Load
document.getElementById('settingTtlSeconds').value = 
    configData.execution?.ttl_seconds || 300;

// Save
'execution.ttl_seconds': parseInt(document.getElementById('settingTtlSeconds').value)
```

---

## Валидация

### Проверки при сохранении:
- **Минимум:** 30 секунд (защита от слишком малого TTL)
- **Максимум:** 86400 секунд = 24 часа (защита от "забытых" ордеров)
- **Шаг:** 30 секунд (удобные значения: 30s, 60s, 120s, 300s...)

### HTML5 валидация:
```html
<input type="number" min="30" max="86400" step="30" value="300">
```

---

## Backward Compatibility

✅ **Полная обратная совместимость:**
- Если в конфиге нет `ttl_seconds` → используется default 300
- Существующие конфиги с `time_in_force: "GTC"` работают без изменений
- IOC/FOK ордера корректно обрабатываются (TTL игнорируется)
- Market ордера не затронуты (как и раньше instant registration)

---

## Testing Scenarios

### Scenario 1: GTC Order with TTL
1. Создать Limit GTC ордер
2. Ордер добавлен в pending с TTL=300s
3. Через 300s → ордер не исполнился → бот отменяет
4. Логируется как "expired"

### Scenario 2: IOC Order without TTL
1. Создать Limit IOC ордер
2. Ордер добавлен в pending с TTL=None
3. Биржа либо исполняет немедленно, либо отменяет
4. Бот мониторит результат (Filled или Cancelled)
5. TTL проверка не срабатывает (нет TTL)

### Scenario 3: PostOnly Order with TTL
1. Включить post_only (автоматически устанавливает PostOnly)
2. Ордер добавлен в pending с TTL=300s
3. Если может исполниться как taker → биржа отменит
4. Если добавлен в стакан как maker → работает как GTC с TTL

---

## Summary

✅ **Time in Force настройки полностью актуальны**  
✅ **TTL применяется только к GTC/PostOnly** (логически корректно)  
✅ **IOC/FOK обрабатываются биржей** (без TTL)  
✅ **Добавлена настройка TTL в UI** (30-86400 сек)  
✅ **Обновлены tooltips** для ясности работы  
✅ **Полная обратная совместимость** с существующими конфигами  

---

**Автор:** GitHub Copilot  
**Дата:** 2024-02-16  
**Связанные документы:** [ORDER_MONITORING_IMPLEMENTATION.md](ORDER_MONITORING_IMPLEMENTATION.md)
