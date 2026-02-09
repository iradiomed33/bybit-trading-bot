# TASK-UI-003: Реальные realtime-апдейты через WebSocket

**Статус:** ✅ ВЫПОЛНЕНО  
**Дата:** 2026-02-09  
**Приоритет:** P1

## Проблема

WebSocket отправлял только `initial_balance` и `initial_status` при подключении, дальше никаких обновлений баланса/позиций не было.

**Результат:** UI показывал статичные данные, не обновлялся в реальном времени.

---

## Решение

### 1. Добавлена фоновая задача в WebSocket

**Файл:** `api/app.py`, функция `websocket_endpoint()` (строки ~1300-1380)

Добавлена async функция `send_periodic_updates()`, которая:
- Запускается в фоне при подключении WebSocket клиента
- Каждые **3 секунды** отправляет апдейты
- Отменяется при отключении клиента

```python
async def send_periodic_updates():
    """Отправка апдейтов баланса и позиций каждые 3 секунды"""
    while True:
        try:
            await asyncio.sleep(3)  # Апдейты каждые 3 секунды
            
            # Получаем данные из БД
            db = Database()
            cursor = db.conn.cursor()
            
            # Запрос баланса и позиций...
            
            # Отправляем апдейт баланса
            await websocket.send_json({
                "type": "account_balance_updated",
                "balance": { ... },
            })
            
            # Отправляем апдейт позиций
            await websocket.send_json({
                "type": "positions_updated",
                "positions": [...],
            })
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error sending periodic updates: {e}")
```

**Lifecycle фоновой задачи:**
```python
# Запуск при подключении
update_task = asyncio.create_task(send_periodic_updates())

try:
    while True:
        # Основной цикл обработки сообщений...
except:
    pass
finally:
    # Остановка при отключении
    update_task.cancel()
    await update_task
```

### 2. Добавлены новые типы WebSocket сообщений

#### `account_balance_updated`

Отправляется **каждые 3 секунды** (пока клиент подключён).

**Структура:**
```json
{
  "type": "account_balance_updated",
  "balance": {
    "total_balance": 10000.0,
    "available_balance": 9500.0,
    "position_value": 500.0,
    "unrealized_pnl": 150.0,
    "currency": "USDT",
    "margin_balance": 500.0
  }
}
```

#### `positions_updated`

Отправляется **каждые 3 секунды** (пока клиент подключён).

**Структура:**
```json
{
  "type": "positions_updated",
  "positions": [
    {
      "symbol": "BTCUSDT",
      "side": "Buy",
      "size": 0.1,
      "entry_price": 45000.0,
      "mark_price": 46000.0,
      "pnl": 100.0,
      "pnl_pct": 2.22
    }
  ]
}
```

### 3. UI обработчики обновлены

**Файл:** `static/js/app.js`, функция `handleWebSocketMessage()` (строки ~407-445)

**Добавлены обработчики:**

```javascript
case 'account_balance_updated':
    // Realtime обновление баланса
    updateBalanceInfo(data.balance);
    break;

case 'positions_updated':
    // Realtime обновление позиций
    updatePositionsTable(data.positions);
    // Обновляем счётчик позиций
    if (document.getElementById('positionCount')) {
        document.getElementById('positionCount').textContent = data.positions.length;
    }
    break;
```

---

## Тестирование

### Модульный тест

**Файл:** `test_ui_003_ws_updates.py`

**Результат:**
```
======================================================================
ТЕСТ TASK-UI-003: Realtime WebSocket Updates
======================================================================

[1/2] Проверка логики periodic updates...
✓ Логика periodic updates работает
  - account_balance_updated: ✓ (total=10000.0, pnl=200.0)
  - positions_updated: ✓ (2 позиций)
    • BTCUSDT: Buy, PnL=100.00 (2.22%)
    • ETHUSDT: Sell, PnL=100.00 (1.67%)

[2/2] Проверка UI обработчиков...
  ✓ account_balance_updated: найден
  ✓ positions_updated: найден
  ✓ updateBalanceInfo: найден
  ✓ updatePositionsTable: найден
✓ UI обработчики добавлены

======================================================================
✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ
======================================================================
```

### Acceptance Criteria

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| На вкладке Account баланс обновляется "живьём" | ✅ | Каждые 3 секунды через WebSocket |
| Позиции обновляются без ручных действий | ✅ | Каждые 3 секунды через WebSocket |
| Нет задержек/зависаний UI | ✅ | Async задача не блокирует основной цикл |

---

## Проверка в боевом режиме

### Как проверить

1. Запустить API:
   ```bash
   python run_api.py
   ```

2. Открыть UI: `http://localhost:8000`

3. Перейти на вкладку **"Аккаунт"**

4. Открыть DevTools (F12) → вкладка **Network** → фильтр **WS**

5. Проверить WebSocket сообщения:
   - При подключении: `initial_balance`, `initial_status`
   - Каждые 3 сек: `account_balance_updated`, `positions_updated`

### Пример console.log

```
[WS] Connected
[WS] ← initial_balance
[WS] ← initial_status
[WS] ← account_balance_updated (+ баланс обновлён)
[WS] ← positions_updated (+ таблица обновлена)
... (каждые 3 секунды)
```

---

## Технические детали

### Почему 3 секунды?

- **Слишком часто (<1 сек):** Избыточная нагрузка на БД/сеть
- **Слишком редко (>10 сек):** UI кажется "мёртвым"
- **3 секунды:** Баланс между realtime и производительностью

### Graceful Shutdown

При отключении клиента:
1. WebSocket вызывает `finally` блок
2. `update_task.cancel()` отменяет фоновую задачу
3. `await update_task` ждёт корректного завершения
4. Клиент удаляется из `connected_clients`

### Thread Safety

- Используется `asyncio.create_task()` (не threading)
- База данных открывается/закрывается в каждой итерации
- Нет race conditions (single-threaded event loop)

---

## Ограничения текущей реализации

⚠️ **Данные всё ещё из SQLite, а не с биржи**

Это будет исправлено в **TASK-UI-001**, которая:
- Заменит SQLite-запросы на вызовы `AccountClient.get_wallet_balance()`
- Получит реальные позиции через `AccountClient.get_positions()`
- Обновит `mark_price` в реальном времени

### Текущее поведение

- ✅ WebSocket отправляет апдейты каждые 3 секунды
- ✅ UI обновляется в реальном времени
- ⚠️ Данные **из SQLite** (могут быть устаревшими)
- ⚠️ Баланс "демо 10000$" (хардкод)

### После внедрения TASK-UI-001

- ✅ WebSocket + **реальные данные с биржи**
- ✅ Актуальный баланс, PnL, позиции
- ✅ Полноценный realtime мониторинг

---

## Возможные улучшения (Future)

### 1. Интеграция с Private WebSocket Bybit

Вместо polling БД каждые 3 секунды:
- Подписаться на `position` topic Bybit Private WS
- Транслировать апдейты **мгновенно** при изменениях на бирже

**Файл:** `exchange/private_ws.py` (уже существует)

**Пример:**
```python
from exchange.private_ws import PrivateWebSocket

private_ws = PrivateWebSocket(
    api_key=...,
    api_secret=...,
    on_position=lambda pos: broadcast_to_clients({
        "type": "positions_updated",
        "positions": [transform_position(pos)]
    }),
)
private_ws.start()
```

### 2. Throttling / Debounce

Если позиций много и они часто меняются:
- Собирать апдейты в батчи
- Отправлять не чаще 1 раз в секунду

### 3. Subscribe/Unsubscribe

Клиент может подписаться только на нужные каналы:
```javascript
ws.send(JSON.stringify({
    type: "subscribe",
    channels: ["balance", "positions"]
}))
```

Сейчас все апдейты отправляются всем клиентам.

---

## Файлы изменены

- `api/app.py` — добавлена фоновая задача `send_periodic_updates()`
- `static/js/app.js` — добавлены обработчики `account_balance_updated`, `positions_updated`

## Файлы созданы

- `test_ui_003_ws_updates.py` — модульный тест

---

## Коммит

```bash
git add api/app.py static/js/app.js test_ui_003_ws_updates.py TASK_UI_003_COMPLETE.md
git commit -m "feat(ws): TASK-UI-003 - add realtime WebSocket updates

- Add background task send_periodic_updates() (every 3 seconds)
- Send account_balance_updated and positions_updated messages
- Add UI handlers for realtime balance/positions updates
- Add test_ui_003_ws_updates.py for validation

Acceptance criteria:
✓ Balance updates in realtime without user actions
✓ Positions table refreshes every 3 seconds
✓ No UI freezes or delays"
```

---

## Связанные задачи

- **TASK-UI-001** (P0) — Получение реальных данных с биржи (вместо SQLite/демо)
- **TASK-UI-002** (P0) — ✅ Исправлена несовместимость схемы позиций

---

**Автор:** GitHub Copilot  
**Версия API:** v1.0  
**WebSocket Protocol:** v1.1 (realtime updates)
