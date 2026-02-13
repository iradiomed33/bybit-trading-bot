# Адаптивное сопровождение позиций по режиму (Regime-Adaptive Position Management)

## Статус: Частичная реализация

### Что реализовано ✅

1. **Конфигурация** (`config.yaml`)
   - `position_management.regime_profiles` - профили параметров по режимам
   - Поддержка `trend`, `range`, `high_vol`, `default` профилей
   - Параметры: `breakeven_trigger`, `trailing_offset_percent`, `time_stop_minutes`

2. **Режим в сигнале**
   - MetaLayer._get_signal_weighted() добавляет `regime` и `regime_scores` в финальный сигнал
   - Информация о режиме доступна при обработке сигнала

3. **Логирование**
   - Режим логируется в structured logs
   - Доступен для анализа decision-making

### Что требует доработки 🔧

#### Integration points:

1. **TradingBot._process_signal()**
   ```python
   # При входе в позицию - извлечь regime из сигнала
   regime = signal.get("regime", "unknown")
   
   # Передать в position_state metadata
   position_metadata = {
       "regime": regime,
       "regime_scores": signal.get("regime_scores"),
       "entry_timestamp": time.time(),
   }
   ```

2. **PositionManager / StopLossTakeProfitManager**
   ```python
   # При инициализации/обновлении BE/Trailing
   def get_regime_params(self, position_metadata):
       regime = position_metadata.get("regime", "unknown")
       profiles = self.config.get("position_management.regime_profiles", {})
       
       if not profiles.get("enabled"):
           return self._get_default_params()
       
       # Маппинг regime label на profile
       profile_map = {
           "trend_up": "trend",
           "trend_down": "trend",
           "range": "range",
           "high_vol": "high_vol",
           "choppy": "range",  # Treat choppy as range
       }
       
       profile_name = profile_map.get(regime, "default")
       profile = profiles.get(profile_name, profiles.get("default", {}))
       
       return {
           "breakeven_trigger": profile.get("breakeven_trigger", 1.5),
           "trailing_offset_percent": profile.get("trailing_offset_percent", 1.0),
           "time_stop_minutes": profile.get("time_stop_minutes", 60),
       }
   ```

3. **PositionStateManager**
   - Добавить `regime` и `regime_metadata` в Position schema
   - Сохранять в базу при создании позиции

### Пример использования

```yaml
# config.yaml
position_management:
  regime_profiles:
    enabled: true
    
    trend:
      breakeven_trigger: 2.0        # Дольше держим в тренде
      trailing_offset_percent: 1.5
      time_stop_minutes: 90
    
    range:
      breakeven_trigger: 1.0        # Быстрее BE в range
      trailing_offset_percent: 0.7
      time_stop_minutes: 45
```

## DoD для полной реализации

- [ ] Добавить `regime` в PositionState schema (database)
- [ ] TradingBot сохраняет regime при открытии позиции
- [ ] PositionManager извлекает параметры из `regime_profiles`
- [ ] Логи показывают выбранный profile
- [ ] Тесты: trend позиция → используется trend profile

## Обходное решение (MVP)

На текущий момент можно использовать:
1. Анализировать логи с `regime_label` при входе
2. Вручную настроить базовые параметры для основного режима торговли
3. Использовать single profile (без адаптации)

Полная реализация — отдельная задача (requires DB schema changes + position management refactor).
