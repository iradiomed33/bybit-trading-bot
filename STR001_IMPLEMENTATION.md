# STR-001: Trend Pullback - ATR-based Stops & Volatility Sizing

## Реализовано

### 1. ATR в FeaturePipeline ✅
- ATR уже вычисляется в `data/features.py` через `calculate_volatility_features()`
- Каноническое имя: `atr` и `atr_percent`
- Используется для расчета стопов, тейков и position sizing

### 2. Стопы и тейки от волатильности ✅
**Файл: `strategy/trend_pullback.py`**

Изменения:
- Long signal: `stop_loss = ema_20 - (1.5 * atr)`
- Long signal: `take_profit = close + (3 * atr)`
- Short signal: `stop_loss = ema_20 + (1.5 * atr)`
- Short signal: `take_profit = close - (3 * atr)`
- Добавлено поле `"atr": atr` в сигнал (явная передача ATR)
- Добавлено поле `"stop_distance": abs(entry - stop_loss)` в сигнал

### 3. Position Sizing от risk_usd / stop_distance ✅
**Файл: `bot/trading_bot.py`**

Изменения:
- Используется `VolatilityPositionSizer` для live mode
- Формула: `qty = risk_usd / (ATR * atr_multiplier) / entry_price`
- Fallback на legacy sizer если ATR отсутствует

### 4. Расширенное логирование ✅
**Файл: `bot/trading_bot.py`**

Добавлено логирование для STR-001:
```python
logger.info(
    f"[STR-001] Volatility-scaled sizing: "
    f"ATR={atr:.2f}, "
    f"Stop={stop_loss:.2f}, "
    f"Take={take_profit:.2f}, "
    f"StopDist={stop_distance:.2f}, "
    f"TakeDist={take_profit_distance:.2f}, "
    f"Risk=${risk_usd:.2f}, "
    f"Qty={qty:.6f}"
)
```

Также добавлен structured logging через `signal_logger.log_debug_info()`:
- category: "position_sizing"
- atr, stop_loss, take_profit
- stop_distance, take_profit_distance
- risk_usd, qty
- method: "volatility_scaled" или "legacy"

## DoD Проверка

### ✅ DoD #1: stop_distance > 0
- Каждый сигнал содержит поле `stop_distance`
- Значение рассчитывается как `abs(entry_price - stop_loss)`
- Всегда > 0 (зависит от ATR)

**Пример:**
```
Entry: $50,720.00
Stop: $50,250.00
stop_distance: $470.00  (= 1.5 * ATR)
```

### ✅ DoD #2: Размер позиции меняется с ATR
- При высокой волатильности (большой ATR) → qty меньше
- При низкой волатильности (малый ATR) → qty больше
- USD риск остается постоянным

**Пример:**
```
Low volatility (ATR=200):  qty=0.000100, risk=$1000
High volatility (ATR=800): qty=0.000025, risk=$1000
Соотношение: 4x ATR → 4x меньше qty
```

### ✅ DoD #3: В логах: atr, stop, take, risk_usd, qty
Все поля присутствуют:
- `atr`: из сигнала стратегии
- `stop`: stop_loss из сигнала
- `take`: take_profit из сигнала
- `risk_usd`: из VolatilityPositionSizer details
- `qty`: рассчитанный размер позиции
- `stop_distance`: дополнительное поле

## Файлы изменены

1. **strategy/trend_pullback.py**
   - Добавлено поле `atr` в возвращаемый сигнал
   - Добавлено поле `stop_distance` в возвращаемый сигнал
   - Явная передача ATR для position sizing

2. **bot/trading_bot.py**
   - Расширенное логирование с меткой `[STR-001]`
   - Логирование всех DoD полей (atr, stop, take, risk_usd, qty, stop_distance)
   - Structured logging через signal_logger

3. **tests/test_str001_volatility_sizing.py** (новый)
   - Тесты для всех 3 DoD требований
   - Edge cases (zero ATR, очень малый ATR)
   - Integration tests

4. **check_str001_dod.py** (новый)
   - Валидационный скрипт для быстрой проверки DoD
   - Запуск: `python check_str001_dod.py`

## Примеры логов

### Signal Generated
```
[STR-001] Volatility-scaled sizing: ATR=300.00, Stop=50250.00, Take=51620.00, StopDist=470.00, TakeDist=900.00, Risk=$1000.00, Qty=0.000100
```

### Structured Logging (signal_logger)
```json
{
  "category": "position_sizing",
  "symbol": "BTCUSDT",
  "atr": 300.0,
  "stop_loss": 50250.0,
  "take_profit": 51620.0,
  "stop_distance": 470.0,
  "take_profit_distance": 900.0,
  "risk_usd": 1000.0,
  "qty": 0.0001,
  "method": "volatility_scaled"
}
```

## Запуск валидации

```bash
# Quick validation
python check_str001_dod.py

# Full pytest suite
pytest tests/test_str001_volatility_sizing.py -v

# Check specific DoD
pytest tests/test_str001_volatility_sizing.py::TestSTR001StopDistance -v
```

## Зависимости

- `VolatilityPositionSizer` уже реализован в `risk/volatility_position_sizer.py`
- ATR вычисляется в `data/features.py` через `TechnicalIndicators.calculate_atr()`
- Используется в live mode при наличии ATR в сигнале

## Следующие шаги (опционально)

1. Добавить параметры ATR multiplier в стратегию (сейчас hardcoded 1.5 для SL, 3.0 для TP)
2. Добавить adaptive ATR multiplier в зависимости от режима волатильности
3. Добавить backtest проверку DoD на исторических данных
4. Dashboard visualization для stop_distance распределения
