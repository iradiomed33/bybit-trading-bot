# Observability: Логирование кандидатов и решений MetaLayer

## Реализовано ✅

### Structured Logging Categories

MetaLayer._get_signal_weighted() логирует все этапы decision-making через `signal_logger.log_debug_info()`:

#### 1. **regime_scoring** - Оценка режима рынка
```json
{
  "category": "regime_scoring",
  "regime": "trend_up",
  "regime_scores": {
    "trend_score": 0.75,
    "range_score": 0.25,
    "volatility_score": 0.30,
    "chop_score": 0.15,
    "regime_label": "trend_up",
    "confidence": 0.75,
    "reasons": ["strong_adx", "ema_aligned_up"],
    "values": {
      "adx": 35.0,
      "atr_percent": 2.5,
      "bb_width": 0.045,
      ...
    }
  }
}
```

#### 2. **strategy_analysis** - Анализ стратегий (когда нет кандидатов)
```json
{
  "category": "strategy_analysis",
  "regime": "range",
  "active_strategies": ["TrendPullback", "Breakout", "MeanReversion"],
  "candidates_count": 0,
  "market_conditions": {
    "adx": 15.0,
    "close": 42500.0,
    "volume_z": 0.5,
    ...
  }
}
```

#### 3. **candidate_scoring** - Все кандидаты + scoring
```json
{
  "category": "candidate_scoring",
  "regime": "trend_up",
  "total_candidates": 2,
  "valid_candidates": 1,
  "rejected_candidates": 1,
  "candidates": [
    {
      "strategy": "TrendPullback",
      "signal": "long",
      "raw_confidence": 0.70,
      "scaled_confidence": 0.70,
      "strategy_weight": 1.5,  // Высокий вес в trend
      "mtf_multiplier": 0.85,
      "final_score": 0.893,     // 0.70 * 1.5 * 0.85
      "rejected": false,
      "rejection_reasons": [],
      "reasons": ["ema_pullback", "volume_confirmation"]
    },
    {
      "strategy": "MeanReversion",
      "signal": "long",
      "raw_confidence": 0.65,
      "scaled_confidence": 0.585,  // scaled down
      "strategy_weight": 0.3,       // Низкий вес в trend
      "mtf_multiplier": 1.0,
      "final_score": 0.176,
      "rejected": true,
      "rejection_reasons": ["no_trade_zone_atr"],  // Отклонён hygiene filter
      "reasons": ["oversold_rsi", "vwap_distance"]
    }
  ]
}
```

#### 4. **final_selection** - Выбранный сигнал
```json
{
  "category": "final_selection",
  "regime": "trend_up",
  "selected_strategy": "TrendPullback",
  "final_score": 0.893,
  "raw_confidence": 0.70,
  "scaled_confidence": 0.70,
  "strategy_weight": 1.5,
  "mtf_multiplier": 0.85
}
```

### Rejection Reasons (reason_codes)

Все отклонения имеют snake_case коды:

**Hygiene Filters:**
- `no_trade_zone_spread` - Превышен максимальный спред
- `no_trade_zone_atr` - Превышен максимальный ATR%
- `anomaly_block` - Обнаружена аномалия данных
- `orderbook_invalid` - Невалидный стакан

**MTF Filters:**
- `mtf_score_below_threshold` - MTF score ниже порога

**Meta-level:**
- `all_candidates_rejected` - Все кандидаты не прошли фильтры
- `meta_conflict` - Конфликт сигналов (legacy)

### Aggregation (Счётчики)

`_summarize_rejections()` создаёт summary отклонений:
```json
{
  "rejection_summary": {
    "no_trade_zone_atr": 3,
    "mtf_score_below_threshold": 1,
    "anomaly_block": 1
  }
}
```

## Примеры использования

### 1. Анализ отклонённых кандидатов
```bash
# Grep логов по категории
grep '"category":"candidate_scoring"' logs/signal_*.log | jq '.candidates[] | select(.rejected==true)'
```

### 2. Топ причин отклонения
```bash
grep '"rejection_summary"' logs/signal_*.log | jq '.values.rejection_summary' | jq -s 'add'
```

### 3. Сравнение scores стратегий по режимам
```bash
grep '"category":"candidate_scoring"' logs/signal_*.log | \
  jq '{regime: .regime, candidates: [.candidates[] | {strategy, final_score}]}'
```

### 4. Win-rate по стратегиям
После исполнения можно коррелировать:
- `final_selection.selected_strategy`
- Результат сделки (из execution logs)

## Расширения (Future)

1. **In-memory metrics aggregation**
   ```python
   class MetricsCollector:
       strategy_selections = Counter()
       rejection_reasons = Counter()
       regime_distribution = Counter()
   ```

2. **Prometheus metrics export**
   ```python
   meta_layer_candidates_total.labels(strategy="TrendPullback").inc()
   meta_layer_rejections.labels(reason="no_trade_zone_atr").inc()
   ```

3. **Dashboard integration**
   - Real-time candidate scores chart
   - Rejection reasons pie chart
   - Strategy selection по режимам

## JSON Log Structure

Все `signal_logger.log_debug_info()` записываются в:
- `logs/signal_<YYYY-MM-DD>.log` (или configurable path)
- Формат: JSON per line (JSONL)
- Парсинг: `jq`, `pandas.read_json(lines=True)`, ELK stack

## Testing Observability

См. [tests/test_weighted_routing.py](../tests/test_weighted_routing.py) для примеров проверки логов.
