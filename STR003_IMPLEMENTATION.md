# STR-003: Entry Confirmation - "Вход по подтверждению"

## Проблема

Старая логика: вход сразу при касании EMA уровня → высокий риск ложных входов в боковике или продолжении коррекции.

**STR-003 решение**: требовать подтверждение rejection паттерна или использовать лимитки с TTL.

## Реализовано

### 1. Параметр entry_mode ✅

**Файл**: `strategy/trend_pullback.py`

```python
def __init__(self, entry_mode="confirm_close", limit_ttl_bars=3):
    # entry_mode: "immediate" | "confirm_close" | "limit_retest"
```

**Три режима входа**:

1. **immediate** - старая логика (вход сразу при касании уровня)
2. **confirm_close** - требует подтверждение закрытием (по умолчанию)
3. **limit_retest** - генерирует лимитку на уровне EMA с TTL

### 2. Метод _check_entry_confirmation() ✅

**Логика подтверждения для LONG**:
- Предыдущая свеча закрылась **ниже** EMA (`prev_close < ema_level`)
- Текущая свеча закрылась **выше** EMA (`current_close > ema_level`)
- ✅ Это rejection паттерн - цена протестировала уровень и отскочила

**Логика подтверждения для SHORT**:
- Предыдущая свеча закрылась **выше** EMA (`prev_close > ema_level`)
- Текущая свеча закрылась **ниже** EMA (`current_close < ema_level`)
- ✅ Bearish rejection паттерн

### 3. Structured Logging ✅

**Rejection logging**:
```python
signal_logger.log_filter_check(
    filter_name=f"Entry Confirmation (STR-003: {self.entry_mode})",
    symbol=symbol,
    passed=entry_confirmed,
    value=confirmation_details,
    threshold="Rejection pattern or limit setup"
)

logger.info(
    f"[STR-003] Signal rejected: no_entry_confirmation | "
    f"Symbol={symbol} | Mode={self.entry_mode} | Details={confirmation_details}"
)
```

**Confirmation details в сигнале**:
```python
signal = {
    "signal": "long",
    "entry_mode": "confirm_close",  # STR-003
    "confirmation": {
        "mode": "confirm_close",
        "confirmed": True,
        "prev_close": 49900,
        "current_close": 50300,
        "ema_level": 50100,
        "prev_below_ema": True,
        "current_above_ema": True
    },
    ...
}
```

### 4. Limit Order Mode ✅

При `entry_mode="limit_retest"`:
- Сигнал всегда подтверждается (для генерации лимитки)
- Добавляются поля:
  - `limit_order=True`
  - `target_price=ema_level` (цена лимитки)
  - `ttl_bars=N` (время жизни заявки в барах)

**Execution layer** должен:
1. Разместить limit order по `target_price`
2. Отслеживать время жизни (TTL)
3. Отменить если не исполнилась за N баров

## Примеры использования

### Пример 1: Режим confirm_close (по умолчанию)

```python
from strategy.trend_pullback import TrendPullbackStrategy

strategy = TrendPullbackStrategy(
    min_adx=15.0,
    entry_mode="confirm_close"  # Требует подтверждение
)

# Сценарий: LONG
# Bar 1: close=49900, EMA=50100 (ниже EMA - pullback)
# Bar 2: close=50300, EMA=50100 (выше EMA - rejection!)
# ✅ Генерирует LONG сигнал

# Сценарий без подтверждения:
# Bar 1: close=50050, EMA=50100 (около EMA)
# Bar 2: close=50080, EMA=50100 (все еще около EMA)
# ❌ Rejection не обнаружен - сигнал отклонен
```

### Пример 2: Immediate mode (старая логика)

```python
strategy = TrendPullbackStrategy(
    min_adx=15.0,
    entry_mode="immediate"  # Вход сразу при касании
)

# Любое касание EMA → entry (опасно в боковике!)
```

### Пример 3: Limit retest mode (maker)

```python
strategy = TrendPullbackStrategy(
    min_adx=15.0,
    entry_mode="limit_retest",
    limit_ttl_bars=3  # TTL = 3 бара
)

# Генерирует сигнал:
signal = {
    "signal": "long",
    "limit_order": True,
    "target_price": 50100,  # EMA level
    "ttl_bars": 3,
    "confirmation": {
        "mode": "limit_retest",
        "target_price": 50100,
        "ttl_bars": 3
    }
}

# Execution layer:
# 1. Размещает лимитку на 50100
# 2. Ждет исполнения 3 бара
# 3. Если не исполнилась → отменяет
```

## Entry Rule - Детальное описание

### LONG Confirmation (confirm_close mode)

**Условие**: `prev_close < ema_level AND current_close > ema_level`

**Интерпретация**:
- Тренд вверх (EMA20 > EMA50)
- Цена откатилась к EMA20 и ПРОБИЛА его вниз (prev candle)
- Но закрылась обратно ВЫШЕ EMA20 (current candle)
- Это показывает что уровень EMA20 выступил как поддержка
- Rejection подтверждает силу тренда

**Визуализация**:
```
Price
  ^
  |     current_close (50300) ← Закрылась выше EMA ✅
  |    /
  |   /
EMA ─┼─────────────────────── (50100)
  |  \
  |   \
  |    prev_close (49900) ← Была ниже EMA
  |
  └──────────────> Time
      Bar -1    Bar 0 (current)
```

### SHORT Confirmation (confirm_close mode)

**Условие**: `prev_close > ema_level AND current_close < ema_level`

**Интерпретация**:
- Тренд вниз (EMA20 < EMA50)
- Цена откатилась к EMA20 и ПРОБИЛА его вверх
- Но закрылась обратно НИЖЕ EMA20
- EMA20 выступил как сопротивление
- Bearish rejection подтверждает нисходящий тренд

## Тестирование

### Синтетические данные для валидации

**Test 1: LONG confirmation**
```python
import pandas as pd
from strategy.trend_pullback import TrendPullbackStrategy

df = pd.DataFrame({
    'close': [51000, 49900, 50300],  # Pullback → Rejection
    'ema_20': [50500, 50100, 50100],
})

strategy = TrendPullbackStrategy(entry_mode="confirm_close")
confirmed, details = strategy._check_entry_confirmation(
    df, symbol="TEST", is_long=True, ema_level=50100
)

assert confirmed == True
assert details['prev_below_ema'] == True  # 49900 < 50100
assert details['current_above_ema'] == True  # 50300 > 50100
```

**Test 2: Rejection без подтверждения**
```python
df = pd.DataFrame({
    'close': [51000, 50100, 50200],  # Оба выше EMA
})

confirmed, _ = strategy._check_entry_confirmation(
    df, symbol="TEST", is_long=True, ema_level=50100
)

assert confirmed == False  # Нет rejection паттерна
```

**Test 3: Parameter validation**
```python
# Valid modes
s1 = TrendPullbackStrategy(entry_mode="immediate")
s2 = TrendPullbackStrategy(entry_mode="confirm_close")
s3 = TrendPullbackStrategy(entry_mode="limit_retest")

# Invalid mode
try:
    TrendPullbackStrategy(entry_mode="invalid")
    assert False, "Should raise ValueError"
except ValueError:
    pass  # Expected
```

## DoD Validation

### ✅ DoD #1: Entry rule описан явно и покрыт тестом на синтетических данных

**Entry rule**:
- **confirm_close**: Требует rejection паттерн (prev close на одной стороне EMA, current close на другой)
- **limit_retest**: Лимитка на уровне EMA с TTL
- **immediate**: Вход сразу при pullback (без подтверждения)

**Тесты**: `test_str003.py`, `test_str003_simple.py`
- Test 1: Параметр entry_mode валидируется
- Test 2: LONG confirmation работает (rejection pattern)
- Test 3: SHORT confirmation работает
- Test 4: Rejection без паттерна отклоняется
- Test 5: Limit retest mode генерирует лимитку

### ✅ DoD #2: Есть параметр entry_mode: confirm_close / limit_retest

```python
class TrendPullbackStrategy:
    def __init__(
        self,
        entry_mode: str = "confirm_close",  # ✅ Parameter exists
        limit_ttl_bars: int = 3,
    ):
        # Validation
        if entry_mode not in ["immediate", "confirm_close", "limit_retest"]:
            raise ValueError(f"Invalid entry_mode: {entry_mode}")
        
        self.entry_mode = entry_mode
        self.limit_ttl_bars = limit_ttl_bars
```

**Supported values**:
- `"immediate"` - старая логика
- `"confirm_close"` - подтверждение rejection (по умолчанию)
- `"limit_retest"` - лимитка с TTL

## Интеграция

### В bot/trading_bot.py

Сигналы теперь содержат:
```python
signal = {
    "entry_mode": "confirm_close",
    "confirmation": {...},
    "limit_order": True,  # если limit_retest
    "target_price": 50100,  # если limit_retest
    "ttl_bars": 3,  # если limit_retest
}
```

### Execution layer (для limit_retest)

**TODO** (будущая работа):
1. Обнаружить `limit_order=True` в сигнале
2. Разместить limit order по `target_price`
3. Отслеживать TTL: отменить если не исполнилась за `ttl_bars` баров
4. Логировать результат (filled / expired)

## Рекомендации

### Когда использовать каждый режим

| Mode | Когда использовать | Pros | Cons |
|------|-------------------|------|------|
| **immediate** | Testing, агрессивная торговля | Больше сигналов | Много ложных входов |
| **confirm_close** | Production (по умолчанию) | Качественные входы, меньше ложных | Меньше сигналов |
| **limit_retest** | Maker rebates, точные входы | Лучшая цена, комиссия | Может не исполниться |

### Настройка для разных условий

**Волатильный рынок**:
```python
# Требуй четкого rejection
strategy = TrendPullbackStrategy(
    entry_mode="confirm_close",
    min_adx=20.0  # Более сильный тренд
)
```

**Спокойный рынок, maker strategy**:
```python
# Используй лимитки
strategy = TrendPullbackStrategy(
    entry_mode="limit_retest",
    limit_ttl_bars=5,  # Больше времени на исполнение
    min_adx=15.0
)
```

**Тестирование / агрессивный режим**:
```python
# Старая логика
strategy = TrendPullbackStrategy(
    entry_mode="immediate"
)
```

## Метрики для мониторинга

**Логи для анализа**:
```bash
# Сколько отклонено по STR-003
grep "STR-003.*rejected: no_entry_confirmation" logs/signals_*.log | wc -l

# Детали rejection
grep "STR-003" logs/signals_*.log | grep "prev_close\|current_close"

# Limit orders (если limit_retest)
grep "limit_order.*True" logs/signals_*.log
```

**Ожидаемые показатели** (confirm_close vs immediate):
- Количество сигналов: -30% to -50% (меньше ложных)
- Win rate: +10% to +20% (выше качество)
- Drawdown: -20% to -30% (меньше ложных входов в боковике)

## Файлы изменены

1. **strategy/trend_pullback.py**
   - Добавлен `entry_mode` parameter
   - Добавлен `limit_ttl_bars` parameter
   - Добавлен метод `_check_entry_confirmation()`
   - Интегрирован в `generate_signal()` для LONG и SHORT
   - Логирование [STR-003] rejection
   - Добавлены поля `entry_mode`, `confirmation`, `limit_order` в сигнал

2. **test_str003.py** (новый)
   - Comprehensive DoD validation
   - 6 тестов с синтетическими данными
   - Parameter validation
   - LONG и SHORT confirmation tests
   - Limit retest mode test

3. **test_str003_simple.py** (новый)
   - Упрощенная версия для быстрой проверки
   - 3 основных теста
   - Minimal dependencies

## Следующие шаги

### STR-003 Готово ✅

Все DoD требования выполнены:
- [x] Entry rule описан явно
- [x] Покрыт тестом на синтетических данных
- [x] Параметр entry_mode существует
- [x] Поддержка confirm_close и limit_retest

### Будущие улучшения (P2)

1. **Execution layer для limit orders**
   - Обработка `limit_order=True` signals
   - TTL tracking и auto-cancel
   - Fill rate метрики

2. **Более сложные confirmation patterns**
   - 2-bar rejection (две свечи подтверждают)
   - Volume confirmation on rejection
   - Wick ratio (rejection wicks)

3. **Adaptive entry mode**
   - Auto-switch между confirm_close и limit_retest
   - На основе volatility или spread
   - Machine learning для оптимизации режима

4. **Backtesting сравнение**
   - immediate vs confirm_close vs limit_retest
   - Win rate, Sharpe, drawdown comparison
   - Optimal TTL для limit_retest
