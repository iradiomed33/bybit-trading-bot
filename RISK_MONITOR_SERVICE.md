# Risk Monitor Service - Real-time Risk Management

## Проблема

До реализации RiskMonitorService риск-лимиты работали как "заглушки":
- Использовали локальные счётчики (`daily_pnl`, `current_positions`)
- Не синхронизировались с реальным состоянием на бирже
- Могли быть неточными после рестарта или рассинхрона

## Решение

**RiskMonitorService** - сервис для реал-тайм мониторинга рисков с использованием реальных данных с биржи.

### Основные возможности

1. **Расчёт equity** = wallet_balance + unrealized_pnl
2. **Расчёт realized PnL** за день из executions
3. **Мониторинг всех лимитов** по реальным данным
4. **Автоматический kill-switch** при критических нарушениях
5. **Фоновый поток** для периодической проверки (каждые 30 сек)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                  RiskMonitorService                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  calculate_equity()                                     │
│    ├─> AccountClient.get_wallet_balance() → balance    │
│    └─> AccountClient.get_positions() → unrealized_pnl  │
│                                                         │
│  calculate_daily_realized_pnl()                        │
│    └─> AccountClient.get_executions() → closedPnl      │
│                                                         │
│  get_position_info()                                    │
│    └─> AccountClient.get_positions() → size, leverage  │
│                                                         │
│  count_open_orders()                                    │
│    └─> AccountClient.get_open_orders() → count         │
│                                                         │
│  check_all_limits()                                     │
│    ├─> Собирает все данные выше                        │
│    └─> AdvancedRiskLimits.evaluate() → RiskDecision    │
│                                                         │
│  trigger_kill_switch_if_needed()                       │
│    └─> KillSwitchManager.activate() если CRITICAL      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## API Reference

### RiskMonitorConfig

Конфигурация для мониторинга рисков.

```python
from risk.risk_monitor import RiskMonitorConfig

config = RiskMonitorConfig(
    max_daily_loss_percent=5.0,      # 5% от equity
    max_position_notional=50000.0,   # $50k максимальная позиция
    max_leverage=10.0,                # 10x максимальное плечо
    max_orders_per_symbol=10,         # 10 ордеров на символ
    monitor_interval_seconds=30,      # Проверка каждые 30 сек
    enable_auto_kill_switch=True,     # Авто-триггер kill-switch
)
```

**Параметры:**
- `max_daily_loss_percent` - Максимальный дневной убыток в % от equity
- `max_position_notional` - Максимальный размер позиции в USD
- `max_leverage` - Максимальное разрешённое плечо
- `max_orders_per_symbol` - Максимум открытых ордеров на символ
- `monitor_interval_seconds` - Интервал проверки в секундах
- `enable_auto_kill_switch` - Автоматически триггерить kill-switch при критических нарушениях

### RiskMonitorService

#### Конструктор

```python
from risk.risk_monitor import RiskMonitorService

risk_monitor = RiskMonitorService(
    account_client=account_client,           # AccountClient instance
    kill_switch_manager=kill_switch_manager, # KillSwitchManager instance
    advanced_risk_limits=advanced_risk_limits, # AdvancedRiskLimits instance
    db=db,                                    # Database instance
    symbol="BTCUSDT",                         # Trading symbol
    config=risk_monitor_config,               # RiskMonitorConfig instance
)
```

#### Методы

##### calculate_equity() → Decimal

Рассчитывает текущий equity.

```python
equity = risk_monitor.calculate_equity()
# equity = wallet_balance + unrealized_pnl
```

**Возвращает:** Текущий equity в USD (Decimal)

**Источники данных:**
- `AccountClient.get_wallet_balance("USDT")` → wallet_balance
- `AccountClient.get_positions()` → unrealized_pnl

##### calculate_daily_realized_pnl() → Decimal

Рассчитывает realized PnL за сегодня.

```python
realized_pnl = risk_monitor.calculate_daily_realized_pnl()
```

**Возвращает:** Realized PnL в USD за текущий день (Decimal)

**Источники данных:**
- `AccountClient.get_executions(limit=100)` → executions
- Фильтрация по `execTime >= today_00:00:00`
- Суммирование `closedPnl` минус `execFee`

##### get_position_info() → Dict

Получает информацию о текущей позиции.

```python
pos_info = risk_monitor.get_position_info()
# {
#     "size": Decimal("0.1"),
#     "leverage": Decimal("5.0"),
#     "notional": Decimal("4212.30"),
#     "unrealized_pnl": Decimal("+123.45"),
#     "mark_price": Decimal("42123.0"),
# }
```

**Возвращает:** Dict с информацией о позиции

**Источники данных:**
- `AccountClient.get_positions(symbol=symbol)`

##### count_open_orders(symbol=None) → int

Подсчитывает количество открытых ордеров.

```python
order_count = risk_monitor.count_open_orders()
# 3
```

**Параметры:**
- `symbol` (optional) - Символ для подсчёта (по умолчанию используется self.symbol)

**Возвращает:** Количество открытых ордеров (int)

**Источники данных:**
- `AccountClient.get_open_orders(symbol=symbol)`

##### check_all_limits() → Dict

Проверяет все риск-лимиты по реальным данным.

```python
check_result = risk_monitor.check_all_limits()
# {
#     "decision": RiskDecision.ALLOW,
#     "equity": 10250.45,
#     "wallet_balance": 10000.00,
#     "unrealized_pnl": +250.45,
#     "realized_pnl_today": -50.25,
#     "position_notional": 4212.30,
#     "position_leverage": 5.0,
#     "open_orders_count": 3,
#     "violations": [],
#     "warnings": [],
#     "orders_violation": None,
#     "timestamp": datetime(...),
# }
```

**Возвращает:** Dict с результатами проверки

**Поля результата:**
- `decision` - RiskDecision.ALLOW / DENY / STOP
- `equity` - Текущий equity (float)
- `wallet_balance` - Wallet balance (float)
- `unrealized_pnl` - Unrealized PnL (float)
- `realized_pnl_today` - Realized PnL за день (float)
- `position_notional` - USD стоимость позиции (float)
- `position_leverage` - Текущее плечо (float)
- `open_orders_count` - Количество открытых ордеров (int)
- `violations` - Список критических нарушений
- `warnings` - Список предупреждений
- `orders_violation` - Нарушение по количеству ордеров (str или None)
- `timestamp` - Время проверки (datetime)

##### trigger_kill_switch_if_needed(check_result) → bool

Триггерит kill-switch если обнаружены критические нарушения.

```python
triggered = risk_monitor.trigger_kill_switch_if_needed(check_result)
# True if kill switch was activated
```

**Параметры:**
- `check_result` - Результат от `check_all_limits()`

**Возвращает:** True если kill-switch был активирован

**Условия активации:**
- `check_result["decision"] == RiskDecision.STOP`
- `enable_auto_kill_switch == True`

**Действия:**
- Логирует критическое предупреждение
- Вызывает `kill_switch_manager.activate(reason)`
- Сохраняет `trading_disabled=True` в БД

##### run_monitoring_check() → Dict

Выполняет полную проверку мониторинга (check + trigger).

```python
check_result = risk_monitor.run_monitoring_check()
```

**Возвращает:** Результат проверки (то же что `check_all_limits()`)

**Действия:**
1. Вызывает `check_all_limits()`
2. Логирует summary
3. Вызывает `trigger_kill_switch_if_needed()` если нужно

##### start_monitoring()

Запускает фоновый поток мониторинга.

```python
risk_monitor.start_monitoring()
```

**Действия:**
- Создаёт daemon thread
- Запускает `_monitoring_loop()`
- Проверяет лимиты каждые `monitor_interval_seconds` секунд

##### stop_monitoring()

Останавливает фоновый поток мониторинга.

```python
risk_monitor.stop_monitoring()
```

**Действия:**
- Устанавливает `self.running = False`
- Ждёт завершения потока (timeout=5s)

##### get_status() → Dict

Получает текущий статус мониторинга.

```python
status = risk_monitor.get_status()
# {
#     "running": True,
#     "last_equity": 10250.45,
#     "last_wallet_balance": 10000.00,
#     "last_unrealized_pnl": 250.45,
#     "last_realized_pnl_today": -50.25,
#     "config": {...},
# }
```

---

## Проверяемые лимиты

### 1. Max Daily Loss

**Проверка:** `abs(realized_pnl_today) <= equity * max_daily_loss_percent / 100`

**Источник данных:** `calculate_daily_realized_pnl()` из executions

**Пример:**
```
equity = $10,000
max_daily_loss_percent = 5.0%
Лимит = $500

realized_pnl_today = -$300 ✅ OK
realized_pnl_today = -$600 ❌ VIOLATION
```

**Действие при нарушении:**
- Если loss > 80% лимита → `severity="critical"` → **STOP** → Kill Switch
- Иначе → `severity="warning"` → **DENY**

### 2. Max Position Size (Notional)

**Проверка:** `position_notional <= max_position_notional`

**Источник данных:** `get_position_info()["notional"]`

**Пример:**
```
max_position_notional = $50,000

position_notional = $42,000 ✅ OK
position_notional = $55,000 ❌ VIOLATION
```

**Действие при нарушении:**
- Если > 150% лимита → `severity="critical"` → **STOP**
- Иначе → `severity="warning"` → **DENY**

### 3. Max Leverage

**Проверка:** `position_leverage <= max_leverage`

**Источник данных:** `get_position_info()["leverage"]`

**Пример:**
```
max_leverage = 10x

position_leverage = 5x ✅ OK
position_leverage = 15x ❌ VIOLATION
```

**Действие при нарушении:**
- Если > 2x лимита → `severity="critical"` → **STOP**
- Иначе → `severity="warning"` → **DENY**

### 4. Max Orders per Symbol

**Проверка:** `open_orders_count <= max_orders_per_symbol`

**Источник данных:** `count_open_orders()`

**Пример:**
```
max_orders_per_symbol = 10

open_orders_count = 8 ✅ OK
open_orders_count = 12 ❌ VIOLATION
```

**Действие при нарушении:**
- **WARNING** в логах
- Не блокирует торговлю напрямую

### 5. Max Drawdown

**Проверка:** `(max_equity - current_equity) / max_equity * 100 <= max_drawdown_percent`

**Источник данных:** `calculate_equity()` + tracking `max_equity`

**Пример:**
```
max_equity = $10,500
current_equity = $9,500
drawdown = ($10,500 - $9,500) / $10,500 * 100 = 9.52%

max_drawdown_percent = 10% ✅ OK
max_drawdown_percent = 5% ❌ VIOLATION
```

**Действие при нарушении:**
- Если > 80% лимита → `severity="critical"` → **STOP** → Kill Switch
- Иначе → `severity="warning"` → **DENY**

---

## Интеграция в TradingBot

### Инициализация

В `TradingBot.__init__()` для live режима:

```python
if mode == "live":
    risk_monitor_config = RiskMonitorConfig(
        max_daily_loss_percent=5.0,
        max_position_notional=50000.0,
        max_leverage=10.0,
        max_orders_per_symbol=10,
        monitor_interval_seconds=30,
        enable_auto_kill_switch=True,
    )
    
    self.risk_monitor = RiskMonitorService(
        account_client=self.account_client,
        kill_switch_manager=self.kill_switch_manager,
        advanced_risk_limits=self.advanced_risk_limits,
        db=self.db,
        symbol=symbol,
        config=risk_monitor_config,
    )
```

### Запуск

В `TradingBot.run()`:

```python
if self.mode == "live" and self.risk_monitor:
    # Первоначальная проверка
    initial_check = self.risk_monitor.run_monitoring_check()
    
    # Если критические нарушения - не запускаемся
    if initial_check["decision"] == RiskDecision.STOP:
        logger.critical("CRITICAL risk violations! Cannot start.")
        return
    
    # Запускаем фоновый мониторинг
    self.risk_monitor.start_monitoring()
```

### Остановка

В `TradingBot.stop()`:

```python
if self.mode == "live" and self.risk_monitor:
    self.risk_monitor.stop_monitoring()
    logger.info("Risk monitor stopped")
```

---

## Логирование

### INFO уровень

```
INFO: Risk Check: decision=allow, equity=$10250.45, pnl_today=$-50.25
INFO: Risk monitoring started
```

### WARNING уровень

```
WARNING: Too many open orders: 12 > 10
WARNING: Risk limits violated - new trades denied
```

### CRITICAL уровень

```
CRITICAL: 🚨 TRIGGERING KILL SWITCH: Critical risk violations: Daily Loss, Drawdown
CRITICAL: Kill switch activated successfully
CRITICAL: CRITICAL risk violations detected! Cannot start trading.
```

### DEBUG уровень

```
DEBUG: Equity: $10250.45 (wallet=$10000.00 + unrealized=$+250.45)
DEBUG: Realized PnL today: $-50.25
DEBUG: Open orders for BTCUSDT: 3
DEBUG: Running risk monitoring check...
```

---

## Примеры использования

### Пример 1: Ручная проверка лимитов

```python
# Создаём сервис
risk_monitor = RiskMonitorService(
    account_client=account_client,
    kill_switch_manager=None,  # Без авто kill-switch
    advanced_risk_limits=advanced_risk_limits,
    db=db,
    symbol="BTCUSDT",
)

# Проверяем лимиты
check_result = risk_monitor.check_all_limits()

print(f"Decision: {check_result['decision'].value}")
print(f"Equity: ${check_result['equity']:.2f}")
print(f"Daily PnL: ${check_result['realized_pnl_today']:+.2f}")

if check_result['decision'] == RiskDecision.DENY:
    print("⚠ Trading denied due to risk limits")
    for violation in check_result['violations']:
        print(f"  - {violation}")
```

### Пример 2: Фоновый мониторинг

```python
# Создаём с авто kill-switch
config = RiskMonitorConfig(enable_auto_kill_switch=True)

risk_monitor = RiskMonitorService(
    account_client=account_client,
    kill_switch_manager=kill_switch_manager,
    advanced_risk_limits=advanced_risk_limits,
    db=db,
    symbol="BTCUSDT",
    config=config,
)

# Запускаем мониторинг
risk_monitor.start_monitoring()

# Работает в фоне...
# Проверяет каждые 30 секунд
# Автоматически триггерит kill-switch при критических нарушениях

# Остановка
risk_monitor.stop_monitoring()
```

### Пример 3: Проверка перед открытием сделки

```python
# Перед созданием ордера
check_result = risk_monitor.check_all_limits()

if check_result['decision'] != RiskDecision.ALLOW:
    logger.error(f"Cannot trade: {check_result['decision'].value}")
    return

# Можно торговать
order_result = order_manager.create_order(...)
```

---

## Сравнение: До и После

### До (Локальные заглушки)

```python
# Локальные счётчики
self.daily_pnl = 0.0
self.current_positions = []

# Обновление вручную
risk_limits.update_daily_stats(pnl)
risk_limits.add_position(position)

# Проблемы:
# - Не синхронизировано с биржей
# - Неточно после рестарта
# - Может быть рассинхрон
```

### После (Реальные данные)

```python
# Реальные данные с биржи
equity = risk_monitor.calculate_equity()
# equity = wallet_balance + unrealized_pnl (из API)

realized_pnl = risk_monitor.calculate_daily_realized_pnl()
# из executions с биржи

# Преимущества:
# ✅ Всегда актуально
# ✅ Синхронизировано с биржей
# ✅ Точно после рестарта
```

---

## Troubleshooting

### Проблема: "Failed to get wallet balance"

**Причина:** API ключи некорректны или rate limit превышен

**Решение:**
1. Проверить API ключи
2. Увеличить `monitor_interval_seconds`
3. Проверить логи для деталей

### Проблема: Kill switch активируется слишком часто

**Причина:** Лимиты слишком строгие

**Решение:**
1. Увеличить `max_daily_loss_percent`
2. Увеличить `max_drawdown_percent`
3. Или установить `enable_auto_kill_switch=False`

### Проблема: Мониторинг не работает

**Причина:** Мониторинг не запущен

**Решение:**
```python
# Проверить статус
status = risk_monitor.get_status()
print(f"Running: {status['running']}")

# Если False, запустить
if not status['running']:
    risk_monitor.start_monitoring()
```

---

## Best Practices

1. **Настройте лимиты под ваш профиль**
   - Консервативный: 3% daily loss, 5% drawdown
   - Умеренный: 5% daily loss, 10% drawdown
   - Агрессивный: 10% daily loss, 15% drawdown

2. **Мониторьте логи**
   - WARNING - обратить внимание
   - CRITICAL - немедленно проверить

3. **Тестируйте на testnet**
   - Перед production настройте лимиты
   - Проверьте что kill-switch работает

4. **Периодически проверяйте статус**
   ```python
   status = risk_monitor.get_status()
   print(f"Last equity: ${status['last_equity']:.2f}")
   print(f"Last PnL today: ${status['last_realized_pnl_today']:+.2f}")
   ```

5. **Используйте разумные интервалы**
   - Слишком часто (< 10s) → rate limits
   - Слишком редко (> 60s) → медленная реакция
   - Оптимально: 30s

---

## Заключение

RiskMonitorService обеспечивает:
- ✅ Реал-тайм мониторинг рисков
- ✅ Реальные данные с биржи
- ✅ Автоматическую защиту через kill-switch
- ✅ Полный контроль над лимитами
- ✅ Надёжность после рестарта

Это критически важный компонент для безопасной торговли в live режиме.
