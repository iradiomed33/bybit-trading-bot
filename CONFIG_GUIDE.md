# 🔧 КОНФИГУРАЦИЯ БОТА

Все настройки бота хранятся в файле [config/bot_settings.json](config/bot_settings.json) и управляются через команду `python cli.py config`.

## 📋 Команды управления конфигурацией

### Показать всю конфигурацию
```bash
python cli.py config show
```

### Показать раздел конфигурации
```bash
python cli.py config section risk_management
python cli.py config section strategies
python cli.py config section meta_layer
```

### Получить конкретное значение
```bash
python cli.py config get trading.symbol
python cli.py config get risk_management.position_risk_percent
python cli.py config get strategies.TrendPullback.confidence_threshold
```

### Установить конкретное значение
```bash
# Изменить символ
python cli.py config set trading.symbol ETHUSDT

# Изменить процент риска
python cli.py config set risk_management.position_risk_percent 2.0

# Включить/отключить стратегию
python cli.py config set strategies.Breakout.enabled false
```

### Сохранить конфигурацию
```bash
python cli.py config save
```

### Валидировать конфигурацию
```bash
python cli.py config validate
```

### Сбросить на значения по умолчанию
```bash
python cli.py config reset
# Введите: RESET для подтверждения
```

## 🏗️ Структура конфигурации

### `trading` - Параметры торговли
```json
{
  "symbol": "BTCUSDT",        // Торговый символ
  "mode": "live",              // "paper" или "live"
  "testnet": true,             // Использовать тестнет
  "active_strategies": [...]   // Активные стратегии
}
```

### `market_data` - Рыночные данные
```json
{
  "kline_interval": "60",              // Интервал свечи (минуты)
  "kline_limit": 500,                  // Количество свечей для загрузки
  "orderbook_depth": 50,               // Глубина стакана
  "data_refresh_interval": 12,         // Интервал обновления (сек)
  "derivatives": {
    "fetch_mark_price": true,          // Получать mark price
    "fetch_index_price": true,         // Получать index price
    "fetch_open_interest": true,       // Получать open interest
    "fetch_funding_rate": true         // Получать funding rate
  }
}
```

### `risk_management` - Управление рисками
```json
{
  "position_risk_percent": 1.0,        // Размер позиции (% от баланса)
  "max_leverage": 10.0,                // Максимальное плечо
  "max_position_size": 0.1,            // Максимальный размер позиции (BTC)
  "stop_loss_percent": 2.0,            // Stop Loss (%)
  "take_profit_percent": 5.0           // Take Profit (%)
}
```

### `strategies` - Параметры стратегий

#### TrendPullback
```json
{
  "enabled": true,
  "confidence_threshold": 0.6,   // Минимальная уверенность сигнала
  "min_candles": 20,             // Минимум свечей для анализа
  "lookback": 30                 // Периода для анализа тренда
}
```

#### Breakout
```json
{
  "enabled": true,
  "confidence_threshold": 0.65,
  "lookback": 20,
  "breakout_percent": 0.02      // Процент пробоя уровня
}
```

#### MeanReversion
```json
{
  "enabled": true,
  "confidence_threshold": 0.55,
  "lookback": 30,
  "std_dev_threshold": 2.0      // Пороги стандартного отклонения
}
```

### `meta_layer` - Метаслой (размещение сигналов)
```json
{
  "use_mtf": true,                           // Использовать мульти-таймфрейм
  "mtf_timeframes": ["1m", "5m", "15m", ...], // Таймфреймы для анализа
  "volatility_filter_enabled": true,         // Фильтр волатильности
  "volatility_threshold": 0.02,              // Порог волатильности
  "no_trade_hours": []                       // Часы без торговли (UTC)
}
```

### `execution` - Исполнение ордеров
```json
{
  "order_type": "limit",           // "limit" или "market"
  "time_in_force": "GTC",          // GTC, IOC, FOK, GTX
  "use_breakeven": true,           // Использовать breakeven
  "use_partial_exit": true,        // Частичные выходы
  "partial_exit_percent": 0.5      // % позиции для частичного выхода
}
```

### `api` - Параметры API
```json
{
  "retry_max_attempts": 3,          // Максимум попыток retry
  "retry_backoff_factor": 2.0,      // Множитель exponential backoff
  "retry_initial_delay": 0.5,       // Начальная задержка (сек)
  "retry_max_delay": 10.0,          // Максимальная задержка (сек)
  "request_timeout": 30             // Timeout запроса (сек)
}
```

## 🚀 Примеры использования

### Перейти на ETHUSDT
```bash
python cli.py config set trading.symbol ETHUSDT
python cli.py config set trading.mode paper
python cli.py config save
python cli.py live
```

### Увеличить агрессивность (больше риск)
```bash
python cli.py config set risk_management.position_risk_percent 3.0
python cli.py config set strategies.TrendPullback.confidence_threshold 0.5
python cli.py config save
```

### Отключить некоторые стратегии
```bash
python cli.py config set strategies.Breakout.enabled false
python cli.py config set strategies.MeanReversion.enabled false
python cli.py config save
```

### Проверить текущие настройки риска
```bash
python cli.py config section risk_management
```

## 🔗 Использование конфигурации в коде

```python
from config import get_config

config = get_config()

# Получить значение
symbol = config.get("trading.symbol")
risk_percent = config.get("risk_management.position_risk_percent")

# Получить раздел
strategies = config.get_section("strategies")

# Установить значение
config.set("trading.symbol", "ETHUSDT")
config.save()
```

## 🎯 Предоставление доступа из UI в будущем

Система конфигурации подготовлена для интеграции с веб-интерфейсом:

1. **REST API эндпоинты** (к реализации):
   - `GET /api/config` - получить конфигурацию
   - `GET /api/config/{section}` - получить раздел
   - `POST /api/config/{key}` - обновить значение
   - `POST /api/config/validate` - валидировать

2. **WebSocket события** (к реализации):
   - `config.updated` - конфигурация обновлена
   - `config.reloaded` - конфигурация перезагружена

3. **Веб-панель** (к реализации):
   - Редактирование конфигурации в реальном времени
   - Валидация перед сохранением
   - История изменений
   - Откат на предыдущие версии

---

**Готово к использованию! Начните с: `python cli.py config show`**
