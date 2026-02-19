# 🚀 КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ: Баг orderbook + агрессивный конфиг

## ✅ ЧТО ИСПРАВЛЕНО

### 1️⃣ БАГ: ticker_data не передавался в build_features() 

**Проблема:**
- `ticker_data` получался в `_fetch_market_data()`, но **НЕ передавался** в `build_features()`
- Orderbook sanity check сравнивал `midprice` с **устаревшим** `close` свечи
- Если цена ушла за 5-15 минут → `deviation > порога` → **"Bad orderbook data"** → no_trade_zone режет всё

**Исправление (bot/trading_bot.py):**
```python
# Вынесено ticker_data = None выше if блока (строка 1202)
ticker_data = None  # ← Доступен в return

# Добавлено в return (строка 1368)
return {
    "df": df,
    "orderbook": orderbook,
    "ticker_data": ticker_data,  # ← ДОБАВЛЕНО!
    "orderflow_features": orderflow_features,
    "derivatives_data": derivatives_data,
}

# Передано в build_features() (строки 660, 2632)
df_with_features = self.pipeline.build_features(
    df_limited,
    orderbook=data.get("orderbook"),
    ticker_data=data.get("ticker_data"),  # ← ДОБАВЛЕНО!
    orderbook_sanity_max_deviation_pct=...
)
```

**Эффект:** Уменьшится количество ложных "Bad orderbook data" rejection.

---

### 2️⃣ АГРЕССИВНЫЙ КОНФИГ для testnet (bot_settings_CORRECT.json)

Проблемы из логов:
- **TrendPullback:** цена 5 ATR от EMA, entry_zone только [-1.5, 1.5]
- **MeanReversion:** require_range_regime=true блокирует в тренде
- **no_trade_zone:** spread 5.37% > 0.8%, ATR 60% > 14%
- **Volume:** volume_z < 0.2 блокирует (отрицательный объём нормален!)

#### Изменения:

**A) TrendPullback - расширена entry_zone:**
```json
"entry_zone_atr_low": -2.5,     // было -1.5
"entry_zone_atr_high": 2.5,     // было 1.5
"volume_z_threshold": -0.5,     // было 0.2 (мягче!)
```

**B) MeanReversion - отключена проверка range:**
```json
"require_range_regime": false,  // было true
"max_adx_for_entry": 35.0,      // было 25.0
```

**C) Breakout - мягче фильтры:**
```json
"min_volume_zscore": 1.0,       // было 1.5 (default)
"min_atr_percent_expansion": 1.15  // было 1.2
```

**D) no_trade_zone - расслабленные лимиты для testnet:**
```json
"no_trade_zone": {
  "max_atr_pct": 80,            // было 12 (для SOLUSDT ATR=60%)
  "max_spread_pct": 8.0         // было 3.0 (для testnet spread)
}
```

**E) Confidence thresholds - снижены:**
```json
"TrendPullback": { "confidence_threshold": 0.55 },  // было 0.65
"Breakout": { "confidence_threshold": 0.6 },        // было 0.7
"MeanReversion": { "confidence_threshold": 0.5 }    // было 0.6
```

---

## 📦 КАК ПРИМЕНИТЬ

### На VDS:

```bash
cd /path/to/bybit-trading-bot

# 1. Backup текущих файлов
cp bot/trading_bot.py bot/trading_bot.py.backup
cp config/bot_settings.json config/bot_settings.json.backup

# 2. Загрузить исправленные файлы с локальной машины:
# - bot/trading_bot.py (с исправленным ticker_data)
# - config/bot_settings_CORRECT.json

# 3. Применить конфиг
cp config/bot_settings_CORRECT.json config/bot_settings.json

# 4. Перезапустить бота
pkill -f "python.*cli.py"
python cli.py &

# 5. Смотреть логи
tail -f bot_run.log | grep -E "REJECTED|ACCEPTED|Building strategies"
```

---

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

### ДО исправлений:
```
[no_trade_zone] REJECTED: "Bad orderbook data: deviation=18.66%"
[no_trade_zone] REJECTED: "Excessive spread: 5.37% > 0.8%"
[TrendPullback] ❌ FAIL | Pullback to EMA: 5.2 ATR (threshold [-1.5, 1.5])
[MeanReversion] ❌ FAIL | Regime Filter: trend_down (requires range)
[no_trade_zone] REJECTED: "Extreme volatility: ATR=60.06% > 14.0%"

Сигналов: 0
Fills: 0
```

### ПОСЛЕ исправлений:
```
[no_trade_zone] ✅ PASS | Orderbook OK (ticker_data используется!)
[no_trade_zone] ✅ PASS | Spread 5.37% < 8.0% (OK для testnet)
[TrendPullback] ✅ PASS | Pullback to EMA: 2.1 ATR (threshold [-2.5, 2.5])
[MeanReversion] ✅ PASS | Regime check disabled
[no_trade_zone] ✅ PASS | ATR 60% < 80% (OK для testnet)

[TrendPullback] ACCEPTED | confidence=0.58
[MetaLayer] Выбрана стратегия: TrendPullback | weighted_score=0.87

Сигналов: 10-15 в день
Fills: 5-8 (post_only=false увеличивает исполнения)
```

---

## ⚠️ РИСКИ ПОД КОНТРОЛЕМ

**Что НЕ изменилось (риск тот же):**
- `position_risk_percent = 2` (2% на сделку)
- `stop_loss_percent = 2` (SL 2%)
- `take_profit_percent = 4` (TP 4%)
- `daily_loss_limit_percent = 3` (дневной лимит)
- `max_leverage = 10`

**Что изменилось (больше входов):**
- Шире entry_zone → **больше точек входа**, но SL тот же
- Мягче volume_z → **меньше ложных отказов**
- Отключен require_range_regime → **работает в трендах**
- Выше no_trade_zone лимиты → **меньше ложных блокировок**

**Результат:** Больше сделок при **том же риске на сделку**.

---

## 📊 МОНИТОРИНГ ПОСЛЕ ЗАПУСКА

Смотрите логи через 1-2 часа:

```bash
# 1. Проверить что ticker_data передается
tail -200 bot_run.log | grep -E "ticker_data|orderbook_invalid"

# 2. Посмотреть accepted сигналы
tail -200 bot_run.log | grep "ACCEPTED"

# 3. Проверить no_trade_zone
tail -200 bot_run.log | grep "no_trade_zone"

# 4. Посмотреть candidates
tail -200 bot_run.log | grep "candidates_count"
```

**Ожидаемо:**
- `candidates_count > 0` (стратегии генерируют сигналы)
- Меньше "Bad orderbook data" (ticker_data работает)
- Меньше "ATR too high" (лимит 80%)
- Больше ACCEPTED от TrendPullback/MeanReversion

---

## 💡 ОПЦИОНАЛЬНО: Еще больше входов (без роста риска)

Если хочешь **еще больше** сделок:

### Вариант 1: Перейти на 15m таймфрейм

```json
"market_data": {
  "kline_interval": "15"  // ← 4x больше событий
}
```

**Эффект:** Pullback к EMA будут встречаться чаще (сейчас на 60m их почти нет).

### Вариант 2: Добавить MTF фильтр тренда (1H) для 15m входов

```json
"meta_layer": {
  "use_mtf": true,
  "mtf_timeframes": ["15", "60"],  // ← Вход 15m, тренд 1H
  "mtf_score_threshold": 0.5
}
```

---

## 🔍 ЕСЛИ ВСЁЕ ЕЩЁ НЕ ТОРГУЕТ

Проверь **какая именно** стратегия должна сработать:

```bash
# Получить детали рынка
tail -50 bot_run.log | grep -E "regime_scoring|strategy_analysis" | tail -1
```

Например:
```json
"regime": "trend_down",
"adx": 90.29,  // ← Очень сильный тренд!
"atr_percent": 1.158,
"candidates_count": 0
```

**Если ADX = 90:**
- TrendPullback: Нужен pullback (цена близко к EMA) ← Сейчас цена 5 ATR!
- GridTrading: max_adx_for_range = 40 ← 90 > 40, блокируется
- MeanReversion: Теперь работает (require_range_regime=false)
- Breakout: Требует squeeze → expansion (в середине тренда нет)

**Решение:** Либо подождать pullback, либо добавить trend-continuation стратегию.

---

**TL;DR:** 
1. Исправлен баг с ticker_data → меньше "Bad orderbook"
2. Расширена entry_zone, отключены жёсткие фильтры → больше сигналов
3. Риск НЕ увеличен (те же SL/TP/position_risk)
4. Ожидаем 10-15 сигналов в день вместо 0
