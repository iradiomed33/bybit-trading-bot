# Reconciliation Service - State Synchronization

## Проблема

После рестарта торгового бота локальное состояние (позиции, ордера, исполнения) не синхронизировалось с биржей. Это приводило к:
- Бот не знал о существующих позициях
- Неактуальная информация об ордерах
- Пропущенные executions
- Рассинхрон между локальным и реальным состоянием

## Решение: ReconciliationService

`ReconciliationService` - это сервис для периодической сверки локального состояния с биржей через REST API.

### Функциональность

1. **Сверка позиций** - сравнение локальных позиций в `PositionManager` с позициями на бирже
2. **Сверка ордеров** - сравнение активных ордеров в БД с открытыми ордерами на бирже
3. **Сверка исполнений** - проверка пропущенных executions
4. **Автоматическая коррекция** - обновление локального состояния при обнаружении рассинхрона
5. **Фоновая периодическая проверка** - каждые N секунд (по умолчанию 60)

## Архитектура

```
┌─────────────────────┐
│   TradingBot        │
│                     │
│  on startup:        │
│  run_reconciliation │
│  start_loop()       │
│                     │
│  on stop:           │
│  stop_loop()        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ReconciliationService│
│                     │
│ ┌─────────────────┐ │
│ │ Background      │ │
│ │ Thread          │ │
│ │ (60s interval)  │ │
│ └────────┬────────┘ │
│          │          │
│          ▼          │
│ ┌─────────────────┐ │
│ │run_reconciliation│ │
│ └────────┬────────┘ │
└──────────┼──────────┘
           │
           ├─► reconcile_positions()
           ├─► reconcile_orders()
           └─► reconcile_executions()
```

## API Reference

### Инициализация

```python
from execution.reconciliation import ReconciliationService

service = ReconciliationService(
    client=rest_client,              # BybitRestClient
    position_manager=position_mgr,   # PositionManager
    db=database,                     # Database
    symbol="BTCUSDT",                # Trading symbol
    reconcile_interval=60,           # Seconds between reconciliations
)
```

### Основные методы

#### `run_reconciliation()`
Выполняет полную сверку состояния.

```python
service.run_reconciliation()
```

Вызывает:
1. `reconcile_positions()`
2. `reconcile_orders()`
3. `reconcile_executions()`

#### `start_loop()`
Запускает фоновый поток для периодической сверки.

```python
service.start_loop()
# Сверка будет выполняться каждые reconcile_interval секунд
```

#### `stop_loop()`
Останавливает фоновый поток.

```python
service.stop_loop()
```

### Методы сверки

#### `reconcile_positions()`
Сверяет позиции с биржей.

**API:** `POST /v5/position/list`

**Логика:**
1. Получает позиции с биржи
2. Сравнивает с `position_manager.positions`
3. При различиях:
   - Обновляет PositionManager
   - Сохраняет в БД
   - Логирует WARNING

**Обнаруживает:**
- Позиции на бирже, которых нет локально → добавляет
- Позиции локально, которых нет на бирже → закрывает
- Различия в size, entry_price → обновляет

#### `reconcile_orders()`
Сверяет открытые ордера.

**API:** `POST /v5/order/realtime`

**Логика:**
1. Получает открытые ордера с биржи
2. Получает активные ордера из БД (`status IN ('New', 'PartiallyFilled')`)
3. При различиях:
   - Ордера есть в БД, но нет на бирже → обновляет статус на 'Cancelled'
   - Ордера есть на бирже, но нет в БД → добавляет в БД

#### `reconcile_executions()`
Сверяет исполнения (fills).

**API:** `POST /v5/execution/list` (limit=50)

**Логика:**
1. Получает последние 50 исполнений с биржи
2. Проверяет наличие в БД
3. Пропущенные исполнения → добавляет в БД

## Интеграция в TradingBot

### При инициализации

```python
# В TradingBot.__init__() для live режима
if mode == "live":
    self.reconciliation_service = ReconciliationService(
        client=rest_client,
        position_manager=self.position_manager,
        db=self.db,
        symbol=symbol,
        reconcile_interval=60,
    )
```

### При старте

```python
# В TradingBot.run()
if self.mode == "live" and self.reconciliation_service:
    logger.info("Running initial reconciliation...")
    self.reconciliation_service.run_reconciliation()
    logger.info("Initial reconciliation complete")
    
    # Запуск фонового потока
    self.reconciliation_service.start_loop()
```

### При остановке

```python
# В TradingBot.stop()
if self.mode == "live" and self.reconciliation_service:
    self.reconciliation_service.stop_loop()
```

## Сценарии использования

### Сценарий 1: Первый запуск

1. Бот запускается в live режиме
2. `run_reconciliation()` выполняется перед началом торговли
3. Загружаются позиции с биржи → `PositionManager`
4. Загружаются ордера → `Database`
5. Загружаются executions → `Database`
6. Бот готов к работе с актуальным состоянием
7. Фоновый поток начинает периодическую сверку

### Сценарий 2: Рестарт с существующей позицией ✅

**Ситуация:** Бот был остановлен, но на бирже есть открытая позиция.

**Поведение:**
1. Бот перезапускается
2. `run_reconciliation()` запускается при старте
3. `reconcile_positions()` обнаруживает позицию на бирже
4. Позиция добавляется в `PositionManager.positions`
5. Позиция сохраняется в БД
6. Логируется: `"Position found on exchange but not locally"`
7. ✅ **Бот корректно "подхватывает" существующую позицию**
8. Может продолжить торговлю без дублирования входа

### Сценарий 3: Обнаружение пропущенного execution

**Ситуация:** WebSocket пропустил execution событие.

**Поведение:**
1. Периодическая сверка (каждые 60 сек)
2. `reconcile_executions()` получает последние 50 executions
3. Обнаруживает execution, которого нет в БД
4. Добавляет execution в БД
5. Логируется: `"Adding missed execution: {exec_id}"`
6. История executions полная

### Сценарий 4: Отменённый ордер не обновлён

**Ситуация:** Ордер отменён вручную через биржу, но локально всё ещё "New".

**Поведение:**
1. Периодическая сверка
2. `reconcile_orders()` получает открытые ордера с биржи
3. Обнаруживает ордер в БД со статусом "New", которого нет на бирже
4. Обновляет статус на "Cancelled" в БД
5. Логируется: `"Order X is active locally but not on exchange"`
6. Локальное состояние синхронизировано

## Database Methods

Для работы ReconciliationService в `Database` добавлены следующие методы:

### `get_active_orders(symbol: str) -> List[Dict]`
Получает активные ордера для символа.

```python
orders = db.get_active_orders("BTCUSDT")
# Вернёт ордера со статусом 'New' или 'PartiallyFilled'
```

### `update_order_status(order_id: str, status: str) -> None`
Обновляет статус ордера.

```python
db.update_order_status("abc123", "Cancelled")
```

### `order_exists(order_id: str) -> bool`
Проверяет наличие ордера в БД.

```python
if db.order_exists("abc123"):
    print("Order exists")
```

### `execution_exists(exec_id: str) -> bool`
Проверяет наличие исполнения в БД.

```python
if not db.execution_exists("exec456"):
    db.save_execution(exec_data)
```

### `save_execution(exec_data: Dict) -> int`
Сохраняет исполнение.

```python
exec_id = db.save_execution({
    "execId": "exec456",
    "orderId": "abc123",
    "symbol": "BTCUSDT",
    "side": "Buy",
    "execPrice": "42000",
    "execQty": "0.001",
    "execFee": "0.042",
    "execTime": 1700000000000,
    "isMaker": False,
})
```

## Логирование

### INFO уровень
- `"ReconciliationService initialized for {symbol}"`
- `"Starting reconciliation..."`
- `"Reconciliation complete"`
- `"Position reconciled for {symbol}"`
- `"Adding missed execution: {exec_id}"`

### WARNING уровень
- `"Position found on exchange but not locally: {symbol} size={size}"`
- `"Position mismatch for {symbol}: local size={} vs exchange size={}"`
- `"Position exists locally but not on exchange: {symbol}"`
- `"Order {order_id} is active locally but not on exchange"`
- `"Order {order_id} exists on exchange but not locally"`

### ERROR уровень
- `"Error reconciling positions: {error}"`
- `"Error reconciling orders: {error}"`
- `"Error reconciling executions: {error}"`
- `"Error in reconciliation loop: {error}"`

## Конфигурация

### Интервал сверки

По умолчанию: **60 секунд**

Изменить можно при инициализации:

```python
service = ReconciliationService(
    ...,
    reconcile_interval=30,  # Сверка каждые 30 секунд
)
```

**Рекомендации:**
- **Высокочастотная торговля:** 30-60 секунд
- **Обычная торговля:** 60-120 секунд
- **Долгосрочная торговля:** 300-600 секунд

## Преимущества

1. **Надёжность после рестарта** ✅
   - Бот подхватывает существующие позиции
   - Не требует ручного вмешательства

2. **Автоматическая синхронизация** ✅
   - Периодическая проверка состояния
   - Нет ручной работы

3. **Обнаружение проблем** ✅
   - Рассинхрон логируется с WARNING
   - Можно отследить в логах

4. **Восстановление пропусков** ✅
   - Пропущенные WebSocket события компенсируются
   - Полная история сохраняется

5. **Безопасность** ✅
   - Предотвращение дублирования позиций
   - Актуальная информация для принятия решений

6. **Гибкость** ✅
   - Настраиваемый интервал
   - Работает независимо от WebSocket

## Ограничения

1. **Rate Limits**
   - Каждая сверка делает 3 API вызова (positions, orders, executions)
   - При интервале 60 сек: ~3 вызова/мин
   - Учитывайте лимиты Bybit API

2. **Задержка обнаружения**
   - Рассинхрон обнаруживается с задержкой до `reconcile_interval`
   - Для критичных данных используйте WebSocket

3. **Не заменяет WebSocket**
   - ReconciliationService - это "safety net"
   - Основной источник данных - WebSocket
   - Reconciliation для восстановления после сбоев

## Тестирование

### Smoke Test

```bash
python test_reconciliation_smoke.py
```

Проверяет:
- ✓ ReconciliationService существует
- ✓ Все методы определены
- ✓ Database имеет необходимые методы
- ✓ TradingBot интегрирован корректно

### Ручное тестирование

1. **Тест рестарта с позицией:**
   ```bash
   # 1. Запустить бота, открыть позицию
   # 2. Остановить бота (позиция остаётся на бирже)
   # 3. Перезапустить бота
   # 4. Проверить логи: "Position found on exchange but not locally"
   # 5. Проверить: position_manager.positions должен содержать позицию
   ```

2. **Тест пропущенного execution:**
   ```bash
   # 1. Отключить WebSocket или симулировать пропуск
   # 2. Выполнить сделку
   # 3. Дождаться reconciliation (60 сек)
   # 4. Проверить логи: "Adding missed execution"
   ```

3. **Тест ручной отмены ордера:**
   ```bash
   # 1. Создать ордер через бота
   # 2. Отменить вручную через UI биржи
   # 3. Дождаться reconciliation
   # 4. Проверить: статус в БД обновлён на "Cancelled"
   ```

## Решение проблем

### "Initial reconciliation failed"

**Причина:** Ошибка при первой сверке (обычно сетевая)

**Решение:**
- Бот продолжит работу
- Следующая сверка через 60 сек
- Проверить сеть и API credentials

### "Error reconciling positions/orders/executions"

**Причина:** Ошибка API или парсинга

**Решение:**
- Проверить логи для детального traceback
- Проверить формат ответа API
- Проверить rate limits

### Высокая нагрузка на API

**Причина:** Слишком частая сверка

**Решение:**
- Увеличить `reconcile_interval` до 120-300 сек
- Проверить не запущено ли несколько ботов

## Best Practices

1. **Всегда запускайте reconciliation при старте**
   - Гарантирует актуальность данных
   - Предотвращает дубликаты

2. **Мониторьте WARNING логи**
   - Частые рассинхроны - признак проблем
   - Могут указывать на проблемы с WebSocket

3. **Настройте алерты**
   - На критичные рассинхроны
   - На ошибки reconciliation

4. **Тестируйте сценарии рестарта**
   - С открытыми позициями
   - С открытыми ордерами
   - После сетевых сбоев

5. **Backup данных БД**
   - ReconciliationService обновляет БД
   - Бэкапы помогут при проблемах

## Заключение

ReconciliationService обеспечивает надёжность торгового бота через автоматическую синхронизацию состояния с биржей. Это критически важно для:

✅ Корректной работы после рестарта  
✅ Восстановления после сбоев WebSocket  
✅ Обнаружения ручных изменений  
✅ Поддержания актуальности данных  

**Результат:** Бот может безопасно перезапускаться и продолжать работу с существующими позициями без риска дублирования или потери данных.
