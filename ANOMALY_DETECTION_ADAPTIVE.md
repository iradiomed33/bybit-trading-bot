# Адаптивная настройка Anomaly Detection

## Проблема

Сейчас пороги **захардкожены** для 1-минутного таймфрейма:
- `anomaly_wick`: тень > 5x тела
- `anomaly_low_volume`: объем < 5% среднего
- `anomaly_gap`: гэп > 3%

**Это неправильно для других таймфреймов!**

## Что нужно изменить

### 1. В `data/features.py` метод `detect_data_anomalies()`

Добавить параметры:
```python
def detect_data_anomalies(
    self, 
    df: pd.DataFrame, 
    kline_interval_minutes: int = 1,
    is_testnet: bool = True
) -> pd.DataFrame:
```

### 2. Адаптивные пороги по таймфрейму

```python
# Чем больше ТФ, тем строже (меньше нормальная волатильность)
if kline_interval_minutes <= 1:
    wick_multiplier = 5.0   # 1min: очень волатильно
    volume_threshold = 0.05  # 5% от среднего
    gap_threshold = 0.03     # 3%
elif kline_interval_minutes <= 5:
    wick_multiplier = 4.5
    volume_threshold = 0.08  # 8%
    gap_threshold = 0.025    # 2.5%
elif kline_interval_minutes <= 15:
    wick_multiplier = 4.0
    volume_threshold = 0.10  # 10%
    gap_threshold = 0.02     # 2%
elif kline_interval_minutes <= 60:
    wick_multiplier = 3.5
    volume_threshold = 0.12  # 12%
    gap_threshold = 0.015    # 1.5%
else:  # 4h, 1d, etc.
    wick_multiplier = 3.0
    volume_threshold = 0.15  # 15%
    gap_threshold = 0.01     # 1%

# Testnet: смягчаем пороги (больше глюков данных)
if is_testnet:
    wick_multiplier += 1.0      # Еще более длинные тени разрешены
    volume_threshold *= 0.5     # Еще ниже объем допустим
    gap_threshold *= 1.5        # Еще больше гэпы разрешены
```

### 3. Передавать параметры из trading_bot.py

```python
# В методе _fetch_market_data() после получения kline_interval
kline_interval_minutes = int(kline_interval)  # "1" -> 1, "60" -> 60, etc.

# При вызове build_features:
df_with_features = self.pipeline.build_features(
    df_limited, 
    orderbook=data.get("orderbook"),
    kline_interval_minutes=kline_interval_minutes,
    is_testnet=self.testnet
)
```

### 4. Обновить build_features() signature

```python
def build_features(
    self,
    df: pd.DataFrame,
    orderbook: Optional[Dict[str, Any]] = None,
    derivatives_data: Optional[Dict[str, float]] = None,
    ticker_data: Optional[Dict[str, Any]] = None,
    orderbook_sanity_max_deviation_pct: float = 3.0,
    kline_interval_minutes: int = 1,  # ← НОВОЕ
    is_testnet: bool = True,          # ← НОВОЕ
) -> pd.DataFrame:
```

И в вызове `detect_data_anomalies`:
```python
# 7. Data Quality (аномалии)
df = self.detect_data_anomalies(
    df, 
    kline_interval_minutes=kline_interval_minutes, 
    is_testnet=is_testnet
)
```

## Таблица порогов

| Таймфрейм | Testnet | Wick | Volume | Gap |
|-----------|---------|------|--------|-----|
| **1 min** | ✅ | 6.0x | 2.5% | 4.5% |
| **1 min** | ❌ | 5.0x | 5.0% | 3.0% |
| **5 min** | ✅ | 5.5x | 4.0% | 3.75% |
| **5 min** | ❌ | 4.5x | 8.0% | 2.5% |
| **1 hour** | ✅ | 4.5x | 6.0% | 2.25% |
| **1 hour** | ❌ | 3.5x | 12.0% | 1.5% |
| **4 hour** | ✅ | 4.0x | 7.5% | 1.5% |
| **4 hour** | ❌ | 3.0x | 15.0% | 1.0% |

## На mainnet

**Когда перейдешь на mainnet:**
1. Передай `is_testnet=False` в trading_bot
2. Пороги станут **в 2 раза строже** автоматически
3. Меньше ложных аномалий, больше качественных сигналов

## Зачем это нужно

**Сейчас (без адаптации):**
- На 1hour ТФ гэп 3% за час = **норма**, но блокируется как аномалия
- Торговля невозможна на крупных таймфреймах

**После адаптации:**
- 1min ТФ: гэп > 3% = аномалия ✅
- 1hour ТФ: гэп > 1.5% = аномалия ✅ (более реалистично)
- Testnet: мягче (гэп > 4.5% на 1min) из-за глюков API
- Mainnet: строже (гэп > 3.0% на 1min) - стабильные данные

## Автоматическая адаптация

После этих изменений бот будет **автоматически** подстраивать пороги:
- При смене ТФ в config.json
- При переходе testnet → mainnet
- Без дополнительной настройки

## Критично для продакшена

На mainnet с hourly/4hour ТФ **обязательно** нужны адаптивные пороги, иначе:
- 90% сигналов блокируются ложными аномалиями
- Бот не торгует вообще
