# Grid Trading - Рекомендации по настройке

## 🎯 Проблема: Нет сигналов Grid Trading

Grid Trading НЕ генерирует сигналы по следующим причинам:

### 1. Строгие фильтры бокового рынка
```json
"require_ranging_market": true,  // Требует подтверждения range
"max_adx_for_range": 25.0,      // ADX < 25 (сейчас может быть выше)
```

**Решение:** Временно отключить `require_ranging_market` для тестирования

### 2. Фильтры Bollinger Bands
```json
"min_bb_width": 0.015,  // Слишком узкий = риск пробоя
"max_bb_width": 0.05,   // Слишком широкий = тренд
```

**Если BB width вне этих границ - сигналов не будет!**

### 3. Защита от пробоя
```json
"enable_breakout_protection": true,  // Блокирует при высоком объёме
"breakout_volume_threshold": 2.0     // Volume Z-score > 2.0
```

### 4. Meta Layer весовые коэффициенты
Grid Trading получает низкий вес если рынок НЕ в range:
```json
"GridTrading": {
  "trend_up": 0.2,      // ← Очень низкий вес в тренде!
  "trend_down": 0.2,
  "range": 2.0,         // ← Высокий только в range
  "choppy": 1.5
}
```

## ✅ Рекомендуемые настройки для ТЕСТИРОВАНИЯ

### Вариант 1: Мягкие фильтры (рекомендуется)
```json
"GridTrading": {
  "enabled": true,
  "require_ranging_market": false,           // ← ОТКЛЮЧИТЬ для теста
  "max_adx_for_range": 35.0,                 // ← Увеличить порог
  "min_bb_width": 0.01,                      // ← Снизить min
  "max_bb_width": 0.08,                      // ← Увеличить max
  "enable_breakout_protection": false,       // ← ОТКЛЮЧИТЬ для теста
  "grid_spacing_percent": 2.0                // ← Больше шаг = меньше уровней
}
```

### Вариант 2: Агрессивные настройки
```json
"GridTrading": {
  "enabled": true,
  "require_ranging_market": false,           // Без фильтров
  "enable_breakout_protection": false,       // Без защиты
  "grid_levels": 15,                         // Меньше уровней
  "grid_spacing_percent": 2.5                // Больше шаг
}
```

## 🔍 Как проверить текущий режим рынка

Запустите бота и смотрите логи:
```powershell
python cli.py

# В другом окне:
Get-Content bot_run.log -Wait -Tail 50 | Select-String "regime|Weighted"
```

Ищите строки типа:
```
[MetaLayer] Regime detected: trend_up | ADX=32.5
[MetaLayer] Weighted routing: TrendPullback=1.5, GridTrading=0.2
```

Если ADX > 25 и режим "trend" - Grid Trading будет иметь вес 0.2 (очень низкий).

## 💡 Не конфликтуют ли стратегии?

**НЕТ!** Стратегии НЕ мешают друг другу. Вот как работает Meta Layer:

### Логика выбора стратегии:
1. Все 4 стратегии генерируют свои сигналы независимо
2. Meta Layer определяет режим рынка (trend/range/choppy)
3. Применяет веса к каждой стратегии
4. Выбирает **ОДНУ стратегию** с наивысшим взвешенным confidence

### Пример:
```
Текущий режим: trend_up (ADX=32)

Сигналы:
- TrendPullback: confidence=0.75 × weight=1.5 = 1.125 ← ПОБЕДИЛ
- GridTrading: confidence=0.80 × weight=0.2 = 0.16
- Breakout: confidence=0.70 × weight=0.7 = 0.49

Выбран: TrendPullback (наивысший weighted score)
```

**Grid Trading просто проигрывает по весам в трендовом рынке!**

## 🚀 Быстрое решение

Создайте файл `config/bot_settings_grid_test.json` с копией настроек, но измените:

```json
"GridTrading": {
  "enabled": true,
  "require_ranging_market": false,
  "enable_breakout_protection": false,
  "max_adx_for_range": 40.0,
  "grid_spacing_percent": 2.0
}
```

И в meta_layer увеличьте веса для всех режимов:
```json
"GridTrading": {
  "base_weight": 1.5,  // ← Увеличить базовый вес
  "regime_multipliers": {
    "trend_up": 0.8,     // ← Увеличить для трендов
    "trend_down": 0.8,
    "range": 2.0,
    "choppy": 1.5
  }
}
```

## 📊 Тест в реальном времени

После изменений запустите:
```powershell
python cli.py

# Смотрите логи:
Get-Content bot_run.log -Wait -Tail 100 | Select-String "GRID|GridTrading"
```

Должны появиться строки:
```
[GRID] BTCUSDT: Range conditions OK
[GRID] BTCUSDT: Auto-detected range [...]
[GRID] BTCUSDT LONG signal | Price=...
```

## ⚙️ Оптимальные настройки для live

После тестирования верните строгие фильтры:
```json
"require_ranging_market": true,
"enable_breakout_protection": true,
"max_adx_for_range": 25.0
```

Это защитит от убытков при пробое диапазона.

---

**TL;DR:** Grid Trading работает, но текущие строгие фильтры блокируют сигналы. Временно отключите фильтры для тестирования.
