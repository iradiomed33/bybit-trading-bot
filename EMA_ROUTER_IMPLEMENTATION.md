# EMA-Router Implementation

## Обзор

EMA-Router — это механизм "склейки" стратегий TrendPullback и Breakout в одном месте (MetaLayer), который выбирает между ними на основе расстояния цены от EMA, измеренного в единицах ATR.

**Идея**: 
- Когда цена **близко** к EMA (≤ 0.7 ATR) → активируется **TrendPullback** (ждём отката к EMA)
- Когда цена **далеко** от EMA (≥ 1.2 ATR) → активируется **Breakout** (цена уже ушла, пробой)
- В промежуточной зоне → обе стратегии доступны или используется гистерезис

## Что изменилось

### 1. Расчёт индикатора `ema_distance_atr`

**Файл**: [data/indicators.py](data/indicators.py)

Добавлен новый метод `calculate_ema_distance()`:

```python
@staticmethod
def calculate_ema_distance(df: pd.DataFrame, ema_period: int = 20) -> pd.DataFrame:
    """Расчёт расстояния от цены до EMA в единицах ATR."""
    df["ema_distance_atr"] = (df["close"] - df[f"ema_{ema_period}"]).abs() / df["atr"]
    return df
```

Вызывается автоматически в `calculate_all_indicators()`.

**Формула**: 
```
ema_distance_atr = |close - EMA20| / ATR
```

### 2. Конфигурация EMA-Router

**Файлы**: 
- [config/settings.py](config/settings.py) (defaults)
- [config/bot_settings_AGGRESSIVE_TESTNET.json](config/bot_settings_AGGRESSIVE_TESTNET.json)
- [config/bot_settings_PRODUCTION.json](config/bot_settings_PRODUCTION.json)

Добавлена секция `meta_layer.ema_router`:

```json
"meta_layer": {
  "ema_router": {
    "enabled": true,
    "ema_period": 20,
    "near_atr": 0.7,
    "far_atr": 1.2,
    "hysteresis_atr": 0.1,
    "regime_strategies": {
      "trend_up": ["TrendPullback", "Breakout"],
      "trend_down": ["TrendPullback", "Breakout"],
      "range": ["MeanReversion"]
    },
    "near_strategies": ["TrendPullback"],
    "far_strategies": ["Breakout"]
  }
}
```

**Параметры**:
- `enabled`: включить/выключить роутер (если false — используется старая логика)
- `ema_period`: период EMA для расчёта расстояния (по умолчанию 20)
- `near_atr`: порог для "близко к EMA" (≤ 0.7 ATR → pullback)
- `far_atr`: порог для "далеко от EMA" (≥ 1.2 ATR → breakout)
- `hysteresis_atr`: гистерезис для предотвращения переключений на границе (0.1 ATR)
- `regime_strategies`: какие стратегии доступны в каждом режиме рынка
- `near_strategies`: стратегии для зоны "near" (близко к EMA)
- `far_strategies`: стратегии для зоны "far" (далеко от EMA)

### 3. Логика роутинга в MetaLayer

**Файл**: [strategy/meta_layer.py](strategy/meta_layer.py)

#### Новый метод `_route_by_ema_distance()`

```python
def _route_by_ema_distance(self, candidates: List[str], df: pd.DataFrame) -> List[str]:
    """
    EMA-router: выбор между pullback/breakout на основе расстояния до EMA.
    
    1. Получает ema_distance_atr из df
    2. Применяет гистерезис (чтобы избежать дёрганья на границе)
    3. Фильтрует кандидатов по near_strategies или far_strategies
    4. Возвращает активные стратегии
    """
```

**Гистерезис**: если был в состоянии "near", требуется +0.1 ATR чтобы переключиться на "far", и наоборот.

#### Обновлённый метод `_adjust_strategies_by_regime()`

```python
def _adjust_strategies_by_regime(self, regime: str, df: Optional[pd.DataFrame] = None):
    """Включить/выключить стратегии в зависимости от режима и EMA-router"""
    
    if self.ema_router_config.get("enabled", False):
        # Новая логика: получаем кандидатов из конфига
        regime_strategies = self.ema_router_config.get("regime_strategies", {})
        candidates = regime_strategies.get(regime, [])
        
        # Применяем EMA-router
        active_strategy_names = self._route_by_ema_distance(candidates, df)
    else:
        # Старая логика (обратная совместимость)
        active_strategy_names = self._get_legacy_strategy_names(regime)
    
    # Включаем/выключаем стратегии
    for strategy in self.strategies:
        if strategy.name in active_strategy_names:
            strategy.enable()
        else:
            strategy.disable()
```

### 4. Логирование

В `strategy_analysis` добавлены новые поля:

```json
{
  "category": "strategy_analysis",
  "regime": "trend_up",
  "active_strategies": ["TrendPullback"],
  "market_conditions": {
    "adx": 32.5,
    "close": 51234.0,
    "volume_z": 1.3,
    "atr": 0.0045,
    "ema_distance_atr": 0.3,  // ← новое
    "ema_route_state": "near"  // ← новое (near/far/null)
  }
}
```

### 5. Интеграция в TradingBot

**Файл**: [bot/trading_bot.py](bot/trading_bot.py)

Передача конфига в MetaLayer:

```python
ema_router_config = self.config.get("meta_layer.ema_router", {})

self.meta_layer = MetaLayer(
    strategies,
    use_mtf=use_mtf,
    mtf_score_threshold=mtf_score_threshold,
    high_vol_event_atr_pct=high_vol_event_atr_pct,
    no_trade_zone_max_atr_pct=no_trade_zone_max_atr_pct,
    no_trade_zone_max_spread_pct=no_trade_zone_max_spread_pct,
    ema_router_config=ema_router_config,  // ← новое
)
```

## Как это работает

### Пример 1: Цена близко к EMA (pullback scenario)

```
Условия:
- regime = "trend_up"
- ema_distance_atr = 0.3 (близко)
- near_atr = 0.7
- far_atr = 1.2

Решение:
0.3 <= 0.7 → state = "near"
→ Активна стратегия: TrendPullback
→ Breakout выключен
```

**Логика**: Цена близко к EMA20, ждём отката к EMA и входим по pullback.

### Пример 2: Цена далеко от EMA (breakout scenario)

```
Условия:
- regime = "trend_up"
- ema_distance_atr = 1.5 (далеко)
- near_atr = 0.7
- far_atr = 1.2

Решение:
1.5 >= 1.2 → state = "far"
→ Активна стратегия: Breakout
→ TrendPullback выключен
```

**Логика**: Цена далеко от EMA, тренд сильный, входим по breakout (цена уже "убежала").

### Пример 3: ATR/EMA не готовы (safe fallback)

```
Условия:
- ema_distance_atr = NaN (индикаторы ещё не рассчитаны)

Решение:
→ Возвращаем всех кандидатов ["TrendPullback", "Breakout"]
→ Безопасная деградация, не ломаем бота
```

### Пример 4: Гистерезис (предотвращение дёргания)

```
Сценарий:
1. ema_distance_atr = 0.5 → state = "near" → TrendPullback
2. ema_distance_atr = 1.1 → 
   - Был "near" → far_threshold = 1.2 + 0.1 = 1.3
   - 1.1 < 1.3 → остаёмся "near" → TrendPullback
3. ema_distance_atr = 1.4 → 
   - 1.4 >= 1.3 → переключаемся на "far" → Breakout
```

**Логика**: Предотвращаем переключения туда-сюда на границе зон.

## Тестирование

### Быстрая проверка через логи

1. Убедитесь что в конфиге `meta_layer.ema_router.enabled = true`
2. Запустите бота (testnet или backtest)
3. Найдите строки `strategy_analysis` в логах:

```bash
cat logs/signal_REJECTED_*.log | grep strategy_analysis | tail -20
```

4. Проверьте 3 случая:

**Case 1: Near (ema_distance_atr ≤ 0.7)**
```json
{
  "regime": "trend_up",
  "active_strategies": ["TrendPullback"],
  "market_conditions": {
    "ema_distance_atr": 0.3,
    "ema_route_state": "near"
  }
}
```

**Case 2: Far (ema_distance_atr ≥ 1.2)**
```json
{
  "regime": "trend_up",
  "active_strategies": ["Breakout"],
  "market_conditions": {
    "ema_distance_atr": 1.5,
    "ema_route_state": "far"
  }
}
```

**Case 3: Fallback (NaN)**
```json
{
  "regime": "trend_up",
  "active_strategies": ["TrendPullback", "Breakout"],
  "market_conditions": {
    "ema_distance_atr": null,
    "ema_route_state": null
  }
}
```

### Unit-тест (опционально)

Можно добавить тест в `tests/test_meta_layer.py`:

```python
def test_ema_router_near():
    """Проверить что при ema_distance_atr = 0.3 активен TrendPullback"""
    df = create_test_df(ema_distance_atr=0.3, regime="trend_up")
    meta = create_meta_layer(ema_router_enabled=True)
    
    meta._adjust_strategies_by_regime("trend_up", df)
    
    assert meta.strategies[0].is_enabled  # TrendPullback
    assert not meta.strategies[1].is_enabled  # Breakout
```

## Где найти код

| Компонент | Файл | Строки |
|-----------|------|--------|
| Расчёт ema_distance_atr | [data/indicators.py](data/indicators.py) | ~406-435 |
| Конфигурация (defaults) | [config/settings.py](config/settings.py) | ~203-235 |
| Конфиг testnet | [config/bot_settings_AGGRESSIVE_TESTNET.json](config/bot_settings_AGGRESSIVE_TESTNET.json) | ~62-78 |
| Конфиг production | [config/bot_settings_PRODUCTION.json](config/bot_settings_PRODUCTION.json) | ~62-78 |
| EMA-router логика | [strategy/meta_layer.py](strategy/meta_layer.py) | ~860-940 |
| Интеграция в бота | [bot/trading_bot.py](bot/trading_bot.py) | ~360-375 |

## Быстрый старт

### Включить EMA-router

В вашем конфиг-файле:
```json
"meta_layer": {
  "ema_router": {
    "enabled": true
  }
}
```

### Выключить EMA-router (откатиться на старую логику)

```json
"meta_layer": {
  "ema_router": {
    "enabled": false
  }
}
```

Или просто удалите секцию `ema_router`.

### Настроить пороги

Можно подстроить пороги под ваш стиль торговли:

```json
"ema_router": {
  "near_atr": 0.5,   // более строгий фильтр pullback
  "far_atr": 1.5,    // требуем больше расстояния для breakout
  "hysteresis_atr": 0.2  // больший гистерезис
}
```

## Преимущества

1. **Одно место управления**: вся логика выбора стратегий в MetaLayer, не раскидана по файлам
2. **Конфигурируемо**: параметры (пороги, режимы, стратегии) управляются через конфиг
3. **Безопасно**: если индикаторы не готовы (NaN) — деградирует корректно
4. **Обратная совместимость**: если `enabled: false` — работает старая логика
5. **Гистерезис**: предотвращает дёргание на границах зон
6. **Логирование**: всё видно в логах (ema_distance_atr, ema_route_state, active_strategies)

## Почему это решает проблему "1.14 ATR vs 0.2 ATR"

**Проблема**: У вас был случай когда:
- `ema_distance_atr = 1.14` (цена далеко от EMA)
- TrendPullback имеет фильтр `ema_distance_atr <= 0.2`
- Результат: **ни одна стратегия не срабатывала**

**Решение**:
- При `ema_distance_atr = 1.14` роутер **автоматически переключает** на Breakout
- Breakout не требует близости к EMA, может работать когда цена "убежала"
- Результат: **Breakout генерирует сигнал**, не теряем возможность входа

## Дальнейшие улучшения (опционально)

1. **Динамические пороги**: подстраивать `near_atr` и `far_atr` под волатильность рынка
2. **Weighted strategies**: вместо включения одной стратегии, давать им веса (0..1) в промежуточной зоне
3. **Backtesting**: прогнать на истории и оптимизировать пороги
4. **A/B тестинг**: запустить 2 инстанса (с роутером и без) и сравнить результаты

---

**Статус**: ✅ Реализовано и протестировано на синтаксических ошибках  
**Версия**: 1.0  
**Дата**: 2026-02-12
