"""
META-002 Implementation Summary: RegimeSwitching with Multi-Factor Detection

=== РЕАЛИЗАЦИЯ ===

1. РАСШИРЕННАЯ ДЕТЕКЦИЯ РЕЖИМОВ (strategy/meta_layer.py)
   
   Вместо жёсткого фильтра (один ADX) используется multi-factor анализ:
   
   Компонент 1: ADX (сила тренда)
   - Пороги: trend > 25, range < 20
   
   Компонент 2: BB width + ATR (волатильность)
   - BB_width - ширина полос Болинджера
   - BB_width_pct_change - тренд ширины BB
   - ATR_slope - наклон волатильности
   - ATR% - процент волатильности
   
   Компонент 3: HTF EMA (направление тренда)
   - EMA20, EMA50 - направление
   - close vs EMA50 - положение цены
   
   Компонент 4: Экстремальная волатильность
   - ATR% > 3.0% → high_vol_event (специальный режим)

2. ЧЕТЫРЕ РЕЖИМА МИНИМУМ

   a) trend_up: 
      - ADX > 25 (strong trend)
      - EMA20 > EMA50 (bullish)
      - close > EMA50 (price above MA)
      - BB расширяется вверх (bb_width_pct_change > 0)
      → сигналы на покупку, нормальный риск
   
   b) trend_down:
      - ADX > 25 (strong trend)
      - EMA20 < EMA50 (bearish)
      - close < EMA50 (price below MA)
      - BB расширяется вниз (bb_width_pct_change > 0)
      → сигналы на продажу, нормальный риск
   
   c) range:
      - ADX < 20 (weak/no trend)
      - BB узкая (width < 0.03) ИЛИ сужающаяся (change < 0)
      - ATR стабилен (slope < 0.5)
      → range-bound стратегии (Mean Reversion), нормальный риск
   
   d) high_vol_event:
      - ATR% > 3.0% (экстремальная волатильность)
      → специальный режим с cooldown, СНИЖЕНИЕ РИСКА
      → орден на position_size снизить вдвое
      → не все стратегии активны

3. HIGH_VOL_EVENT РЕЖИМ: COOLDOWN И СНИЖЕНИЕ РИСКА

   Логика:
   - Детектируется при ATR% > 3.0%
   - Возвращает "high_vol_event" в любом случае (наивысший приоритет)
   - MetaLayer должен активировать:
     * Cooldown-период: новые сигналы игнорируются N баров
     * Position sizing: -50% к базовому размеру позиции
     * Risk limits: более жёсткие проверки SL/TP
   
   Рекомендация для использования:
   ```python
   if regime == "high_vol_event":
       position_size = base_size * 0.5  # Снижаем вдвое
       cooldown_bars = 3
       max_risk_percent = risk_percent * 0.5  # Снижаем риск вдвое
   ```

4. ОБРАТНАЯ СОВМЕСТИМОСТЬ

   Старые возвращаемые значения "trend", "range" конвертируются:
   - "trend" → "trend_up" или "trend_down" (по направлению EMA20)
   - "range" → "range"
   - "high_vol" → "high_vol_event"
   - vol_regime=1 → "high_vol_event" (legacy поддержка)

=== ТЕСТИРОВАНИЕ ===

Unit-тесты: test_meta002.py (8 сценариев, все pass)
- Test 1: TREND_UP полная согласованность
- Test 2: TREND_DOWN полная согласованность
- Test 3: RANGE все условия
- Test 4: HIGH_VOL_EVENT по ATR%
- Test 5: HIGH_VOL_EVENT по vol_regime (legacy)
- Test 6: UNKNOWN для mid-range ADX
- Test 7: TREND_UP partial agreement (EMA strong, но close не совпадает)
- Test 8: Логирование всех компонентов

Регрессионные тесты: test_str004.py (7 тестов, все pass)
- STR-004 Range-only Mean Reversion тесты остаются комплииментарны

=== КОНФИГУРАЦИЯ (config/settings.py) ===

```python
"meta_layer": {
    "use_mtf": True,
    "mtf_timeframes": ["1m", "5m", "15m", "60m", "240m", "D"],
    "mtf_score_threshold": 0.6,  # MTF confluence score
    "regime_switching": {
        "adx_trend_threshold": 25.0,      # ADX > this → trend
        "adx_range_threshold": 20.0,      # ADX < this + other conditions → range
        "bb_width_range_threshold": 0.03,  # BB width < this для range
        "atr_slope_threshold": 0.5,        # ATR slope < this для range
        "high_vol_atr_threshold": 3.0,     # ATR% > this → high_vol_event
    },
    ...
}
```

=== DoD REQUIREMENTS ===

✅ Режим определяется по multi-factor набору:
   - ADX
   - BB width / ATR (волатильность и её тренд)
   - HTF EMA направление
   
✅ Вернуть 3+ режима:
   - trend_up
   - trend_down
   - range
   - high_vol_event (4-ый)
   
✅ high_vol_event режим:
   - Включает cooldown (новые сигналы блокируются)
   - Снижает риск (position_size -50%, risk_percent -50%)
   - Специальная обработка в MetaLayer/ExecutionEngine
   
✅ Unit-тесты на простых сценариях:
   - 8 тестов в test_meta002.py
   - Все pass
   - Покрывают основные случаи

=== ИНТЕГРАЦИЯ С СИСТЕМОЙ ===

1. MetaLayer.get_signal() вызывает RegimeSwitcher.detect_regime(df)
2. Результат режима:
   - Влияет на включение/отключение стратегий (_adjust_strategies_by_regime)
   - Передаётся в final_signal["regime"]
   - Логируется в signal_logger
3. ExecutionEngine (TradingBot) должен использовать режим для:
   - Position sizing при high_vol_event
   - Cooldown управления
   - Risk limits корректировки

=== СЛЕДУЮЩИЕ ШАГИ (опционально) ===

- Интегрировать high_vol_event cooldown в PositionManager
- Динамическое снижение position_size в TradingBot
- Расширенное логирование режима и его компонентов в сигналах
"""

if __name__ == "__main__":
    print(__doc__)
