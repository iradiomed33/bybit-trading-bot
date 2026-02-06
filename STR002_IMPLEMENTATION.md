# STR-002: Liquidation Wick Filter

## Реализовано

### 1. Детекция ликвидационных свечей ✅
**Файл: `data/features.py`**

Метод `detect_liquidation_wicks()` определяет экстремальные свечи по трем критериям:

1. **Большой диапазон**: `candle_range > k * ATR` (по умолчанию k=2.5)
2. **Большие тени**: `max_wick_ratio > threshold` (по умолчанию 0.7 = 70% от диапазона)
3. **Всплеск объёма**: `volume > percentile` (по умолчанию 95th percentile)

**Условие детекции**: `(большой_диапазон ИЛИ большие_тени) И всплеск_объёма`

**Добавленные колонки**:
- `liquidation_wick` (1 = detected, 0 = normal)
- `candle_range_atr` (диапазон свечи в ATR)
- `wick_ratio` (отношение максимальной тени к диапазону)

### 2. Фильтр в TrendPullback стратегии ✅
**Файл: `strategy/trend_pullback.py`**

**Новые параметры конфигурации**:
```python
enable_liquidation_filter: bool = True           # Вкл/выкл фильтр
liquidation_cooldown_bars: int = 3               # Cooldown период (N баров)
liquidation_atr_multiplier: float = 2.5          # Множитель ATR
liquidation_wick_ratio: float = 0.7              # Порог отношения тени
liquidation_volume_pctl: float = 95.0            # Перцентиль объёма
```

**Метод `_check_liquidation_cooldown()`**:
- Проверяет последние N баров на наличие ликвидационных свечей
- Если обнаружена - блокирует вход на cooldown период
- Логирует детальную информацию о свече

### 3. Логирование ✅

**Structured logging** (signal_logger):
```python
signal_logger.log_filter_check(
    filter_name="Liquidation Wick Cooldown (STR-002)",
    symbol=symbol,
    passed=False,
    value={
        "bars_since_liquidation": 2,
        "cooldown_bars": 3,
        "candle_range_atr": 3.5,
        "wick_ratio": 0.8,
    },
    threshold="Cooldown=3 bars"
)
```

**Warning log** (DoD требование):
```
[STR-002] Signal rejected: liquidation_wick_filter | 
Symbol=BTCUSDT | Bars since liquidation=2/3 | 
Candle range=3.50x ATR | Wick ratio=0.80
```

## DoD Проверка

### ✅ DoD #1: В логах видно "rejected: liquidation_wick_filter"

**Пример лога**:
```
2026-02-05 15:19:32 | WARNING | strategy.trend_pullback | 
[STR-002] Signal rejected: liquidation_wick_filter | 
Symbol=BTCUSDT | Bars since liquidation=2/3 | 
Candle range=3.50x ATR | Wick ratio=0.80
```

### ✅ DoD #2: Можно включить/выключить фильтр конфигом

**Включен** (по умолчанию):
```python
strategy = TrendPullbackStrategy(
    min_adx=15.0,
    enable_liquidation_filter=True,  # ✅ Фильтр активен
    liquidation_cooldown_bars=3
)
```

**Выключен**:
```python
strategy = TrendPullbackStrategy(
    min_adx=15.0,
    enable_liquidation_filter=False  # ❌ Фильтр отключен
)
```

## Примеры использования

### Пример 1: Детекция ликвидационной свечи

```python
from data.features import FeaturePipeline

pipeline = FeaturePipeline()

# Данные с ликвидационной свечой
df = pd.DataFrame({
    'close': [50000, 50000, 48500, 50000],  # Большое движение
    'high':  [50100, 50100, 51500, 50100],  # Огромная верхняя тень
    'low':   [49900, 49900, 48000, 49900],  # Большой диапазон
    'open':  [50000, 50000, 50000, 50000],
    'volume':[1000,  1000,  15000, 1000],   # Всплеск объёма 15x
})

df['atr'] = 300.0

# Детектируем
df = pipeline.detect_liquidation_wicks(df)

print(df['liquidation_wick'])
# Output: [0, 0, 1, 0]  # Свеча #2 обнаружена
```

### Пример 2: Фильтрация сигналов

```python
from strategy.trend_pullback import TrendPullbackStrategy

# Стратегия с фильтром
strategy = TrendPullbackStrategy(
    min_adx=15.0,
    enable_liquidation_filter=True,
    liquidation_cooldown_bars=3  # Блокировка на 3 бара
)

# Если в последних 3 барах была ликвидационная свеча
# → сигнал будет отклонен
signal = strategy.generate_signal(df, features)
# Returns None если в cooldown периоде
```

### Пример 3: Настройка параметров детекции

```python
# Более агрессивная детекция (меньше порогов)
strategy = TrendPullbackStrategy(
    enable_liquidation_filter=True,
    liquidation_atr_multiplier=2.0,    # Меньший множитель (легче триггерить)
    liquidation_wick_ratio=0.6,        # Меньший порог теней
    liquidation_volume_pctl=90.0,      # 90th percentile (чаще срабатывает)
    liquidation_cooldown_bars=5        # Дольше блокировка
)
```

## Валидация

### Запуск DoD тестов:
```bash
python validate_str002.py
```

### Отладка детекции:
```bash
python debug_liquidation_detection.py
```

## Файлы изменены

1. **data/features.py**
   - Добавлен метод `detect_liquidation_wicks()`
   - Интегрирован в `build_features()`
   - Добавлены колонки: `liquidation_wick`, `candle_range_atr`, `wick_ratio`

2. **strategy/trend_pullback.py**
   - Добавлены конфигурационные параметры для фильтра
   - Добавлен метод `_check_liquidation_cooldown()`
   - Интегрирован в `generate_signal()` после проверки ADX
   - Логирование rejection через signal_logger

3. **validate_str002.py** (новый)
   - Валидационный скрипт для DoD проверки
   - 4 теста: детекция, конфигурация, rejection, disabled filter

4. **debug_liquidation_detection.py** (новый)
   - Отладочный скрипт для проверки детекции
   - Подробный вывод метрик каждой свечи

## Технические детали

### Формула детекции ликвидационной свечи:

```python
# 1. Диапазон свечи
candle_range = high - low

# 2. Тени
upper_wick = high - max(close, open)
lower_wick = min(close, open) - low
max_wick = max(upper_wick, lower_wick)

# 3. Wick ratio
wick_ratio = max_wick / candle_range

# Условия
large_range = candle_range > (2.5 * ATR)
large_wick = wick_ratio > 0.7
volume_spike = volume > rolling_95th_percentile

# Финальное условие
liquidation_wick = (large_range OR large_wick) AND volume_spike
```

### Cooldown механизм:

```python
# Проверяем последние N баров (включая текущий)
lookback = min(cooldown_bars, len(df))
recent_bars = df.iloc[-lookback:]

# Есть ли ликвидационная свеча?
if recent_bars['liquidation_wick'].sum() > 0:
    # Находим последнюю
    last_liq_idx = recent_bars[recent_bars['liquidation_wick'] == 1].index[-1]
    bars_since = len(df) - (df.index.get_loc(last_liq_idx) + 1)
    
    # Если bars_since < cooldown_bars → блокируем вход
    if bars_since < cooldown_bars:
        return True  # Reject signal
```

## Интеграция с другими стратегиями

Фильтр легко добавить в другие стратегии:

```python
class MyStrategy(BaseStrategy):
    def __init__(self, enable_liquidation_filter=True, cooldown_bars=3):
        self.enable_liquidation_filter = enable_liquidation_filter
        self.cooldown_bars = cooldown_bars
    
    def generate_signal(self, df, features):
        # ... ваша логика ...
        
        # Добавить проверку фильтра
        if self.enable_liquidation_filter:
            if self._check_liquidation_cooldown(df, symbol):
                return None  # Reject
        
        # ... продолжить генерацию сигнала ...
```

## Метрики и мониторинг

**Что логируется**:
- `bars_since_liquidation` - баров с последней ликвидационной свечи
- `candle_range_atr` - диапазон свечи в ATR (сколько раз больше ATR)
- `wick_ratio` - доля тени в диапазоне (0.8 = 80%)
- `cooldown_bars` - настроенный cooldown период

**Для мониторинга**:
```bash
# Найти все rejection по ликвидационным свечам
grep "liquidation_wick_filter" logs/signals.log

# Посчитать количество
grep -c "liquidation_wick_filter" logs/signals.log
```

## Рекомендации

1. **По умолчанию**: `enable_liquidation_filter=True` с `cooldown_bars=3`
2. **Агрессивный режим**: `atr_multiplier=2.0`, `cooldown_bars=5`
3. **Консервативный режим**: `atr_multiplier=3.0`, `cooldown_bars=2`
4. **Тестирование**: Всегда проверять на исторических данных с реальными ликвидациями
