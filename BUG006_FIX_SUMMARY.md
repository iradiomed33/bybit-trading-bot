# Исправление BUG-006: Config partially ignored

## Описание проблемы

**Приоритет:** Medium/High

**Симптомы:**
- Конфиг содержит настройки, но они игнорируются
- `meta_layer.use_mtf` в конфиге не применяется
- `data_refresh_interval` игнорируется, всегда 10 секунд
- `active_strategies` игнорируется, всегда загружаются все 3 стратегии
- Изменения в `config/bot_settings.json` не меняют поведение бота

**Корневые причины:**

1. **MetaLayer создается с дефолтами** (`bot/trading_bot.py:340`):
```python
# СТАРЫЙ КОД:
self.meta_layer = MetaLayer(strategies)
# ← use_mtf НЕ передается, всегда дефолт True
```

2. **Фиксированный sleep** (`bot/trading_bot.py:714`):
```python
# СТАРЫЙ КОД:
time.sleep(10)  # 10 секунд - хардкод!
# ← data_refresh_interval из конфига игнорируется
```

3. **Стратегии хардкодятся** (`cli.py:1263-1270`, `api/app.py`):
```python
# СТАРЫЙ КОД:
strategies = [
    TrendPullbackStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
]
# ← active_strategies из конфига игнорируется
```

## Реализованное решение

### Изменения в коде

**Файл:** `bot/trading_bot.py`

#### 1. Чтение конфига в __init__ (строки 121-124)

```python
# ДОБАВЛЕНО:
# Читаем конфиг для использования настроек
from config.settings import get_config
self.config = get_config()
```

#### 2. Передача use_mtf в MetaLayer (строки 344-349)

```python
# СТАРЫЙ КОД:
self.meta_layer = MetaLayer(strategies)

# НОВЫЙ КОД:
# Читаем настройки meta_layer из конфига
use_mtf = self.config.get("meta_layer.use_mtf", True)
mtf_score_threshold = self.config.get("meta_layer.mtf_score_threshold", 0.6)

logger.info(f"Creating MetaLayer with use_mtf={use_mtf}, mtf_score_threshold={mtf_score_threshold}")
self.meta_layer = MetaLayer(strategies, use_mtf=use_mtf, mtf_score_threshold=mtf_score_threshold)
```

#### 3. Использование data_refresh_interval (строки 721-724)

```python
# СТАРЫЙ КОД:
time.sleep(10)  # 10 секунд

# НОВЫЙ КОД:
# Используем data_refresh_interval из конфига
refresh_interval = self.config.get("market_data.data_refresh_interval", 10)
logger.debug(f"Waiting {refresh_interval} seconds before next iteration...")
time.sleep(refresh_interval)
```

**Файл:** `cli.py`

#### 4. Фильтрация стратегий в paper_command (строки 1262-1288)

```python
# СТАРЫЙ КОД:
strategies = [
    TrendPullbackStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
]

# НОВЫЙ КОД:
# Читаем конфиг
config = get_config()

# Читаем active_strategies из конфига
active_strategy_names = config.get("trading.active_strategies", [
    "TrendPullback", "Breakout", "MeanReversion"
])

# Создаем только активные стратегии
strategy_map = {
    "TrendPullback": TrendPullbackStrategy,
    "Breakout": BreakoutStrategy,
    "MeanReversion": MeanReversionStrategy,
}

strategies = []
for name in active_strategy_names:
    if name in strategy_map:
        strategies.append(strategy_map[name]())
        logger.info(f"Loaded strategy: {name}")
    else:
        logger.warning(f"Unknown strategy in config: {name}")

# Fallback на дефолты если нет стратегий
if not strategies:
    logger.error("No valid strategies configured! Using defaults.")
    strategies = [
        TrendPullbackStrategy(),
        BreakoutStrategy(),
        MeanReversionStrategy(),
    ]
```

#### 5. Аналогично для live_command (строки 1330-1368)

**Файл:** `api/app.py`

#### 6. Фильтрация стратегий в /api/bot/start

Аналогичная логика фильтрации стратегий по `active_strategies` из конфига.

## Результаты

### Тестирование

**Unit тесты:** 7/7 проходят ✅

```bash
pytest tests/test_bug006_fix.py -v
```

- ✅ test_strategy_filtering_logic
- ✅ test_strategy_filtering_empty_config
- ✅ test_strategy_filtering_unknown_strategy
- ✅ test_refresh_interval_value
- ✅ test_refresh_interval_default
- ✅ test_use_mtf_value
- ✅ test_mtf_score_threshold_value

### Демонстрация

Файл: `demo_bug006_fix.py`

```bash
python demo_bug006_fix.py
```

Показывает:
- ❌ СТАРОЕ: конфиг игнорируется
- ✅ НОВОЕ: настройки применяются
- ✅ Примеры использования конфига

## Примеры использования

### Пример 1: Отключить MTF проверки

```json
{
  "meta_layer": {
    "use_mtf": false
  }
}
```

**Эффект:**
- MetaLayer не проверяет multi-timeframe confluence
- Сигналы обрабатываются быстрее
- Меньше API запросов

### Пример 2: Изменить refresh interval

```json
{
  "market_data": {
    "data_refresh_interval": 30
  }
}
```

**Эффект:**
- Обновление данных раз в 30 секунд вместо 12
- Меньше нагрузка на API

### Пример 3: Использовать одну стратегию

```json
{
  "trading": {
    "active_strategies": ["TrendPullback"]
  }
}
```

**Эффект:**
- Загружается только TrendPullbackStrategy
- Другие стратегии не используются
- Быстрее обработка

## Критерии приёмки

- [x] Изменения в config/bot_settings.json реально меняют поведение:
  - [x] symbols - работает (MultiSymbolBot уже использует)
  - [x] refresh interval - применяется
  - [x] use_mtf - применяется
  - [x] список стратегий - фильтруется

## Влияние на систему

**Положительное:**
- ✅ Конфиг теперь работает как ожидается
- ✅ Можно гибко настраивать поведение бота без изменения кода
- ✅ use_mtf позволяет отключить MTF проверки для скорости
- ✅ refresh_interval позволяет контролировать частоту запросов
- ✅ active_strategies позволяет выбирать стратегии

**Обратная совместимость:**
- ✅ Все параметры имеют дефолтные значения
- ✅ Если конфиг не указан, используются разумные дефолты
- ✅ Старые конфиги продолжают работать

## Технические детали

### Config structure

```json
{
  "trading": {
    "active_strategies": ["TrendPullback", "Breakout", "MeanReversion"]
  },
  "market_data": {
    "data_refresh_interval": 12
  },
  "meta_layer": {
    "use_mtf": false,
    "mtf_score_threshold": 0.6
  }
}
```

### Логика фильтрации стратегий

1. Читаем `active_strategies` из конфига
2. Создаем `strategy_map` с доступными стратегиями
3. Для каждого имени из конфига:
   - Если стратегия существует → создаем и добавляем
   - Если нет → логируем warning
4. Если список пустой → используем все стратегии (fallback)

### Когда конфиг загружается

- При создании `TradingBot` в `__init__`
- В CLI команд при старте
- В API endpoint при `/api/bot/start`

## Откат изменений (если потребуется)

```bash
git revert b78a146 715b8da  # Откатить коммиты
```

Но это **не рекомендуется**, т.к. исправление:
- Прошло 7/7 тестов
- Улучшает гибкость конфигурации
- Критерии приёмки выполнены

---

**Дата исправления:** 2026-02-08  
**Автор:** GitHub Copilot Agent  
**Тестирование:** Полное (7/7 тестов)  
**Статус:** ✅ Завершено и проверено
