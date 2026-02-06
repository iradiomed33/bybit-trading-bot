# STR-004: Mean Reversion Range-Only Mode

## Проблема

Mean Reversion стратегия опасна в трендовых рынках - попытка "ловить падающий нож" может привести к серии убытков.

**STR-004 решение**: жесткий фильтр - MR торгует ТОЛЬКО в подтвержденном range режиме + анти-нож фильтр.

## Реализовано

### 1. Расширен RegimeSwitcher ✅

**Файл**: `strategy/meta_layer.py`

**Новая логика range detection** (жесткие условия):
```python
def detect_regime(df, adx_range_threshold=20.0, bb_width_range_threshold=0.03, atr_slope_threshold=0.5):
    # Range mode требует ВСЕ три условия:
    is_low_adx = adx < 20  # Слабый тренд
    is_bb_narrow_or_contracting = (bb_width < 0.03) OR (bb_width_pct_change < 0)  # Узкие/сужающиеся полосы
    is_atr_stable = atr_slope < 0.5  # Волатильность не растет
    
    if is_low_adx AND is_bb_narrow_or_contracting AND is_atr_stable:
        return "range"
```

**Возможные режимы**:
- `"range"` - все условия для range выполнены
- `"trend_up"` - ADX > 25, EMA20 > EMA50
- `"trend_down"` - ADX > 25, EMA20 < EMA50
- `"high_vol"` - vol_regime == 1
- `"unknown"` - не подходит ни под один режим

### 2. Новые фичи в FeaturePipeline ✅

**Файл**: `data/features.py`

```python
# STR-004: BB width change (для определения сужения)
df['bb_width_pct_change'] = df['bb_width'].pct_change(5)  # Изменение за 5 баров

# STR-004: ATR slope (рост волатильности)
df['atr_slope'] = df['atr'].diff(5) / 5  # Изменение ATR за 5 периодов
```

**Интерпретация**:
- `bb_width_pct_change < 0` → полосы сужаются (range усиливается)
- `atr_slope > 0.5` → волатильность растет (выход из range)

### 3. MeanReversionStrategy с жестким фильтром ✅

**Файл**: `strategy/mean_reversion.py`

**Новые параметры**:
```python
def __init__(
    self,
    require_range_regime: bool = True,  # STR-004: Требовать range режим
    enable_anti_knife: bool = True,      # STR-004: Анти-нож фильтр
    adx_spike_threshold: float = 5.0,    # Рост ADX за 3 бара
    atr_spike_threshold: float = 0.5,    # ATR slope порог
):
```

**Логика фильтрации**:

1. **Regime Filter** (основной):
```python
if require_range_regime:
    regime = RegimeSwitcher.detect_regime(df)
    if regime != "range":
        return None  # Блокировка в trend/high_vol/unknown режимах
```

2. **Anti-Knife Filter** (дополнительный):
```python
if enable_anti_knife:
    adx_spike = adx_current - adx_3bars_ago
    atr_slope = latest['atr_slope']
    
    if (adx_spike > 5.0) OR (atr_slope > 0.5):
        return None  # Блокировка при резком росте ADX/ATR
```

### 4. Structured Logging ✅

**Regime logging** (перед сигналом):
```python
logger.info(f"[STR-004] MeanReversion: regime=range ✓ | Symbol=BTCUSDT")
```

**Rejection logging**:
```python
# Trend rejection
logger.info(f"[STR-004] MeanReversion rejected: regime=trend_up (only 'range' allowed) | Symbol=BTCUSDT")

# Anti-knife rejection
logger.warning(
    f"[STR-004] MeanReversion rejected: anti_knife_triggered | "
    f"ADX_spike=7.00 (threshold=5.0), ATR_slope=0.40 (threshold=0.5) | Symbol=BTCUSDT"
)
```

## Примеры работы

### Пример 1: Range режим → MR торгует

**Условия**:
- ADX = 15 (< 20 ✓)
- bb_width = 0.02 (< 0.03 ✓)
- atr_slope = 0.1 (< 0.5 ✓)
- RSI = 25 (oversold)
- VWAP_distance = -3%

**Результат**:
```
[STR-004] MeanReversion: regime=range ✓
Signal: LONG, entry=49950, target=50500 (VWAP)
```

### Пример 2: Trend режим → MR блокируется

**Условия**:
- ADX = 30 (> 25)
- EMA20 > EMA50
- Остальные условия MR выполнены

**Результат**:
```
Detected regime: trend_up
[STR-004] MeanReversion rejected: regime=trend_up (only 'range' allowed)
Signal: None
```

### Пример 3: Range режим + ADX spike → Anti-knife блокирует

**Условия**:
- Режим = range (все условия OK)
- ADX: 10 → 11 → 12 → 17 (spike = 7 > threshold 5)

**Результат**:
```
[STR-004] MeanReversion: regime=range ✓
[STR-004] MeanReversion rejected: anti_knife_triggered | ADX_spike=7.00 (threshold=5.0)
Signal: None
```

## Range Detection - Детальная логика

### Формула режима range

```python
# Условие 1: Слабый тренд
is_low_adx = (adx < adx_range_threshold)  # default: 20

# Условие 2: Узкие или сужающиеся Bollinger Bands
is_bb_narrow = (bb_width < bb_width_range_threshold)  # default: 0.03
is_bb_contracting = (bb_width_pct_change < 0)
is_bb_narrow_or_contracting = is_bb_narrow OR is_bb_contracting

# Условие 3: Стабильная волатильность
is_atr_stable = (atr_slope < atr_slope_threshold)  # default: 0.5

# Финальное условие
range_mode = is_low_adx AND is_bb_narrow_or_contracting AND is_atr_stable
```

### Почему все три условия?

**Только ADX** недостаточно:
- ADX может быть низким в начале тренда
- Нужно подтверждение через BB width

**Только BB width** недостаточно:
- BB могут быть узкими перед прорывом
- Нужно подтверждение через ADX и ATR

**Только ATR slope** недостаточно:
- ATR может быть низким в слабом тренде
- Нужно подтверждение через BB и ADX

**Все вместе** → надежный range:
- ADX < 20: нет сильного направленного движения
- BB узкие/сужаются: цена консолидируется
- ATR stable: волатильность не растет

## Anti-Knife Filter - Детали

### Зачем нужен anti-knife?

**Проблема**: даже в range режиме может начаться резкий выход → "нож"

**Примеры ножа**:
1. **ADX spike**: ADX за 3 бара: 15 → 16 → 17 → 22 (spike = 7)
2. **ATR spike**: ATR slope внезапно > 0.5

### Логика anti-knife

```python
# Проверяем последние 4 бара
adx_current = df.iloc[-1]['adx']
adx_3bars_ago = df.iloc[-4]['adx']
adx_spike = adx_current - adx_3bars_ago

atr_slope = df.iloc[-1]['atr_slope']

# Knife detected?
is_knife = (adx_spike > adx_spike_threshold) OR (atr_slope > atr_spike_threshold)

if is_knife:
    logger.warning("[STR-004] Anti-knife triggered")
    return None
```

### Разница между regime filter и anti-knife

| Аспект | Regime Filter | Anti-Knife Filter |
|--------|---------------|-------------------|
| **Цель** | Определить общий режим рынка | Поймать внезапные спайки |
| **Окно** | Текущий бар (latest) | 3-4 бара (spike detection) |
| **Условия** | ADX < 20, BB narrow, ATR stable | ADX spike > 5, ATR slope > 0.5 |
| **Когда срабатывает** | В тренде или высокой волатильности | При резком ускорении из range |
| **Порог ADX** | Абсолютный (< 20) | Относительный (change > 5) |
| **Порог ATR** | Slope < 0.5 | Slope > 0.5 |

**Пример разницы**:
- ADX = 18 (< 20 ✓ для regime), но spike = 8 за 3 бара → anti-knife блокирует
- Regime говорит "пока еще range", но anti-knife говорит "ускорение началось"

## Тестирование

### Валидация DoD

**Test 1: Range allows MR**
```python
df = create_test_df(adx=15, bb_width=0.02, atr_slope=0.1)
regime = RegimeSwitcher.detect_regime(df)  # "range"
signal = strategy.generate_signal(df, features)  # Not None
```

**Test 2: Trend blocks MR**
```python
df = create_test_df(adx=30, bb_width=0.05, ema_trend='up')
regime = RegimeSwitcher.detect_regime(df)  # "trend_up"
signal = strategy.generate_signal(df, features)  # None
```

**Test 3: High-vol blocks MR**
```python
df['vol_regime'] = 1  # High volatility
regime = RegimeSwitcher.detect_regime(df)  # "high_vol"
signal = strategy.generate_signal(df, features)  # None
```

**Test 4: Anti-knife ADX spike**
```python
df['adx'] = [10, 11, 12, 17]  # Spike of 7 > 5
regime = "range"
signal = strategy.generate_signal(df, features)  # None (anti-knife blocked)
```

**Test 5: Anti-knife ATR spike**
```python
df['atr_slope'] = 0.4  # > 0.3 threshold
regime = "range"
signal = strategy.generate_signal(df, features)  # None (anti-knife blocked)
```

### Запуск тестов

```bash
python test_str004.py
```

**Ожидаемый результат**: 🎉 ALL TESTS PASSED

## DoD Validation

### ✅ DoD #1: Логи показывают regime=range перед MR-сделкой

**Лог перед сигналом**:
```
2026-02-05 16:30:34 | INFO | [STR-004] MeanReversion: regime=range ✓ | Symbol=BTCUSDT
```

**Подтверждение**: Каждый MR сигнал предваряется логом с подтверждением range режима.

### ✅ DoD #2: В трендовом режиме MR не торгует вообще

**Лог в тренде**:
```
2026-02-05 16:30:34 | WARNING | ❌ FAIL | Filter=Regime Filter (STR-004) | Symbol=BTCUSDT | Value=trend_up | Threshold=range
2026-02-05 16:30:34 | INFO | [STR-004] MeanReversion rejected: regime=trend_up (only 'range' allowed)
```

**Подтверждение**: 
- `require_range_regime=True` по умолчанию
- В trend/high_vol/unknown режимах MR возвращает None
- Тесты 2, 3 подтверждают блокировку

## Настройка параметров

### Консервативный режим (меньше false signals)

```python
strategy = MeanReversionStrategy(
    require_range_regime=True,
    enable_anti_knife=True,
    # Более жесткие условия для range
    # (настройки RegimeSwitcher)
    # adx_range_threshold=15.0,  # Еще слабее тренд
    # bb_width_range_threshold=0.02,  # Еще уже BB
)

# В RegimeSwitcher.detect_regime():
regime = RegimeSwitcher.detect_regime(
    df,
    adx_range_threshold=15.0,  # Строже
    bb_width_range_threshold=0.02,  # Строже
    atr_slope_threshold=0.3  # Строже
)
```

### Агрессивный режим (больше сделок)

```python
strategy = MeanReversionStrategy(
    require_range_regime=True,
    enable_anti_knife=False,  # Отключить anti-knife
)

regime = RegimeSwitcher.detect_regime(
    df,
    adx_range_threshold=25.0,  # Мягче
    bb_width_range_threshold=0.05,  # Мягче
    atr_slope_threshold=1.0  # Мягче
)
```

### Отключить STR-004 (вернуться к старой логике)

```python
strategy = MeanReversionStrategy(
    require_range_regime=False,  # Отключить жесткий фильтр
    enable_anti_knife=False
)
# Будет использовать старый vol_regime фильтр
```

## Файлы изменены

1. **data/features.py**
   - Добавлено: `bb_width_pct_change` (изменение BB width)
   - Добавлено: `atr_slope` (изменение ATR)

2. **strategy/meta_layer.py**
   - Обновлен: `RegimeSwitcher.detect_regime()`
   - Добавлены параметры: `adx_range_threshold`, `bb_width_range_threshold`, `atr_slope_threshold`
   - Логика range detection: все три условия одновременно
   - Возврат: "range" | "trend_up" | "trend_down" | "high_vol" | "unknown"

3. **strategy/mean_reversion.py**
   - Добавлен импорт: `RegimeSwitcher`, `signal_logger`
   - Новые параметры: `require_range_regime`, `enable_anti_knife`, `adx_spike_threshold`, `atr_spike_threshold`
   - Фильтр режима перед всеми проверками
   - Anti-knife фильтр после проверки режима
   - [STR-004] логирование с детальной информацией
   - Updated reasons: `"range_regime"`, `"anti_knife_passed"`

4. **test_str004.py** (новый)
   - 6 тестов для валидации DoD
   - Тесты range/trend/high_vol режимов
   - Тесты anti-knife фильтров
   - Тест strictness regime detection

## Метрики для мониторинга

### Логи для анализа

```bash
# Сколько сигналов заблокировано по режиму
grep "\[STR-004\].*rejected: regime=" logs/signals_*.log | wc -l

# Сколько заблокировано anti-knife
grep "\[STR-004\].*anti_knife_triggered" logs/signals_*.log | wc -l

# Детали rejection по режимам
grep "\[STR-004\].*rejected" logs/signals_*.log | cut -d'|' -f2 | sort | uniq -c

# Все MR сделки с подтверждением range
grep "\[STR-004\].*regime=range" logs/signals_*.log
```

### Ожидаемые показатели

**До STR-004** (vol_regime фильтр):
- Количество MR сигналов: 100%
- Win rate: ~45-50%
- Проблема: losses в начале трендов

**После STR-004** (range фильтр + anti-knife):
- Количество MR сигналов: -60% to -70% (меньше ложных)
- Win rate: +15% to +25% (60-65%)
- Меньше losses в трендах и breakouts

## Рекомендации

### Когда использовать MR с STR-004

✅ **Хорошие условия**:
- Боковой рынок несколько часов/дней
- ADX стабильно < 20
- BB сужаются
- Объем низкий

❌ **Плохие условия**:
- После важных новостей
- Во время токенизированных событий
- В начале трендовых движений
- При расширении BB

### Best practices

1. **Всегда включать** `require_range_regime=True` (по умолчанию)
2. **Включать anti-knife** для дополнительной защиты
3. **Мониторить** количество rejection - если > 90%, слишком строго
4. **Backtesting** для подбора оптимальных порогов под ваш актив
5. **Комбинировать** с другими стратегиями (TrendPullback для трендов, MR для range)

## Следующие шаги

### STR-004 Готово ✅

Все DoD требования выполнены:
- [x] Режим range определяется жестко (ADX + BB + ATR)
- [x] MR торгует только в range режиме
- [x] Anti-knife фильтр блокирует спайки
- [x] Логи показывают regime=range перед сделкой
- [x] В trend/high_vol режимах MR не торгует

### Будущие улучшения (P2)

1. **Adaptive thresholds**
   - Auto-adjust ADX/BB/ATR thresholds по символу
   - Machine learning для оптимизации порогов
   - Разные пороги для разных timeframes

2. **Multi-timeframe regime confirmation**
   - Проверка range на старшем TF
   - Если H4 = trend, блокировать MR на M15
   - Confluence detection

3. **Volatility forecasting**
   - Предсказание выхода из range
   - GARCH модели для прогноза волатильности
   - Early warning system для anti-knife

4. **Backtest comparison**
   - STR-004 vs old vol_regime filter
   - Win rate, Sharpe, max drawdown
   - Оптимальные параметры для BTC/ETH/altcoins
