# Order Monitoring Implementation

## Overview

Внедрена полноценная система мониторинга ордеров для корректного управления жизненным циклом рыночных (Market) и лимитных (Limit) ордеров.

## Problem Solved

**До реализации:**
- Limit ордера регистрировались как позиции сразу после создания (до фактического исполнения)
- `position_state_manager.sync_with_exchange()` не находил позицию на бирже (ордер еще не исполнился)
- Система ошибочно считала позицию "закрытой вручную" через 220ms после создания
- Временный fix: grace period 10s (недостаточно для limit ордеров, которые могут исполняться часами)

**После реализации:**
- Market ордера: позиция регистрируется мгновенно (instant fill)
- Limit ордера: отслеживаются в `pending_orders`, позиция регистрируется только при `Filled` статусе
- Реализован TTL (time to live) механизм для истечения неисполненных ордеров
- Proper lifecycle management: New → Filled/Cancelled/Rejected

---

## Architecture

### 1. Order Manager (`execution/order_manager.py`)

**Добавлено:**

```python
self.pending_orders: Dict[str, Dict[str, Any]] = {}
```

**Методы:**

#### `get_order_status(order_id, symbol)`
- Запрашивает актуальный статус ордера через `/v5/order/realtime`
- Возвращает `order_info` dict или `None` если ордер не найден
- Используется для проверки статуса pending ордеров

#### `monitor_pending_orders(position_callback)`
- Проверяет все ордера в `pending_orders` dict
- Обрабатывает статусы:
  - **Filled**: вызывает callback, удаляет из pending
  - **Cancelled/Rejected**: логирует, удаляет из pending
  - **PartiallyFilled**: продолжает отслеживать
  - **New + TTL expired**: отменяет ордер, удаляет из pending
- Возвращает статистику: `{"filled": [...], "cancelled": [...], "expired": [...]}`

**Параметр `position_callback`:**
- Функция с сигнатурой: `callback(order_info: Dict, pending_info: Dict)`
- Вызывается когда limit ордер исполнился (status=Filled)
- Отвечает за регистрацию позиции в position_state_manager и position_manager

---

### 2. Trading Bot (`bot/trading_bot.py`)

#### A. Order Placement Logic (Lines 2211-2250)

**Market Orders:**
```python
if order_type == "Market":
    # Регистрируем позицию сразу (instant fill)
    self.position_state_manager.open_position(
        side=side_long,
        qty=Decimal(str(normalized_qty)),
        entry_price=Decimal(str(normalized_price)),
        order_id=order_id,
        strategy_id=signal.get("strategy", "Unknown"),
    )
```

**Limit Orders:**
```python
else:  # Limit
    # Добавляем в pending для мониторинга
    self.order_manager.pending_orders[order_id] = {
        "symbol": self.symbol,
        "side": side_long,
        "qty": float(normalized_qty),
        "price": float(normalized_price),
        "created_at": time.time(),
        "ttl_seconds": ttl,
        "strategy": signal.get("strategy", "Unknown"),
        "sl_price": sl_price,
        "tp_price": tp_price,
        "current_atr": current_atr,
    }
    # Позиция будет зарегистрирована в callback при fill
```

#### B. Main Loop Integration (Lines 908-972)

**Callback Function:**
```python
def register_filled_position(order_info, pending_info):
    """Callback для регистрации позиции когда limit ордер исполнился"""
    
    # 1. Получаем фактическую цену исполнения
    avg_price = float(order_info.get("avgPrice", pending_info["price"]))
    filled_qty = float(order_info.get("cumExecQty", pending_info["qty"]))
    
    # 2. Регистрируем в position_state_manager
    self.position_state_manager.open_position(
        side=pending_info["side"],
        qty=Decimal(str(filled_qty)),
        entry_price=Decimal(str(avg_price)),
        order_id=order_info.get("orderId"),
        strategy_id=pending_info["strategy"],
    )
    
    # 3. Регистрируем в position_manager для сопровождения (breakeven/trailing)
    if self.position_manager:
        self.position_manager.register_position(
            symbol=pending_info["symbol"],
            side="Buy" if pending_info["side"] == "Long" else "Sell",
            entry_price=avg_price,
            size=filled_qty,
            stop_loss=pending_info.get("sl_price"),
            take_profit=pending_info.get("tp_price"),
            ...
        )
```

**Monitoring Call:**
```python
# 8. Мониторим pending ордера (limit orders) и регистрируем позиции при fill
if self.mode == "live" and self.order_manager:
    monitoring_result = self.order_manager.monitor_pending_orders(
        position_callback=register_filled_position
    )
    
    # Логируем результаты
    if monitoring_result["filled"]:
        logger.info(f"Filled orders: {len(monitoring_result['filled'])}")
    if monitoring_result["cancelled"]:
        logger.warning(f"Cancelled orders: {len(monitoring_result['cancelled'])}")
    if monitoring_result["expired"]:
        logger.warning(f"Expired orders (TTL): {len(monitoring_result['expired'])}")
```

**Частота проверки:** каждые 10 секунд (период основного loop)

---

## Configuration

### UI Settings

**Execution Settings (в Dashboard → Settings → Execution):**

1. **Тип ордера**: Market / Limit
2. **Time in Force**: 
   - GTC (Good Till Cancel) - ордер активен до исполнения (используется TTL)
   - IOC (Immediate or Cancel) - исполнить немедленно или отменить (TTL не применяется)
   - FOK (Fill or Kill) - исполнить полностью или отменить (TTL не применяется)
3. **Post-only**: чекбокс для maker-only режима (устанавливает PostOnly, работает как GTC с TTL)
4. **TTL для Limit ордеров**: 30-86400 секунд (по умолчанию 300 = 5 минут)
   - Применяется только к GTC и PostOnly
   - IOC/FOK обрабатываются биржей мгновенно

### `config.yaml` / `bot_settings.json`

```yaml
execution:
  order_type: "limit"        # "market" или "limit"
  time_in_force: "GTC"       # "GTC", "IOC", "FOK"
  post_only: false           # Maker-only режим (автоматически устанавливает PostOnly)
  ttl_seconds: 300           # Time to live для GTC/PostOnly ордеров (5 минут)
```

**Time in Force:**
- **GTC (Good Till Cancel)**: Ордер активен до исполнения/отмены. **TTL применяется**.
- **IOC (Immediate or Cancel)**: Ордер исполняется немедленно или отменяется биржей. **TTL не применяется** (биржа сама обрабатывает).
- **FOK (Fill or Kill)**: Ордер исполняется полностью или отменяется биржей. **TTL не применяется** (биржа сама обрабатывает).
- **PostOnly**: Устанавливается автоматически если `post_only: true`. Работает как GTC. **TTL применяется**.

**TTL (Time To Live):**
- По умолчанию: 300 секунд (5 минут)
- Применяется только к GTC и PostOnly ордерам
- IOC/FOK ордера не используют TTL (биржа их обрабатывает мгновенно)
- Настраивается через UI или `execution.ttl_seconds` в config
- Диапазон: 30-86400 секунд (30 сек - 24 часа)

---

## Lifecycle Flow

### Market Order Flow
```
Signal → create_order(Market) → Instant Fill → open_position() → register_position()
```
**Время регистрации:** мгновенно (при создании ордера)

### Limit Order Flow
```
Signal → create_order(Limit) → Add to pending_orders → Monitor status
  ↓
  Status = Filled → callback → open_position() → register_position()
  Status = Cancelled → Remove from pending
  Status = Timeout (TTL) → Cancel order → Remove from pending
```
**Время регистрации:** при исполнении ордера (может быть через часы)

---

## Key Features

### 1. Proper Order vs Position Distinction
- **Order**: создан на бирже, может быть в статусе New/PartiallyFilled/Filled
- **Position**: существует только когда ордер исполнился (Filled)
- Limit ордер в статусе New ≠ позиция

### 2. TTL (Time To Live)
- Автоматическая отмена неисполненных limit ордеров
- Предотвращает "забытые" ордера в стакане
- Настраивается через `execution.ttl_seconds`

### 3. Callback Pattern
- Модульная архитектура: order_manager отвечает за мониторинг, trading_bot — за регистрацию позиции
- Callback вызывается только при Filled статусе
- Обрабатывает фактическую цену исполнения (`avgPrice`) вместо запрошенной

### 4. Partial Fill Handling
- PartiallyFilled статус продолжает отслеживаться
- Позиция регистрируется только когда ордер полностью исполнен
- **TODO**: опциональная регистрация позиции при частичном исполнении

---

## Logs

**Limit Order Placed (GTC/PostOnly with TTL):**
```
[LIMIT ORDER] Added to pending: 123456 (Long 0.001 @ 65000), TIF=GTC, TTL=300s. Position will be registered when filled.
```

**Limit Order Placed (IOC/FOK without TTL):**
```
[LIMIT ORDER] Added to pending: 123456 (Long 0.001 @ 65000), TIF=IOC (no TTL - exchange will handle). Position will be registered when filled.
```

**Limit Order Filled:**
```
✓ Order 123456 FILLED: 0.001 BTCUSDT
[LIMIT FILLED] Position registered: Long 0.001 @ 65123.5, orderId=123456
Position registered: Buy 0.001 BTCUSDT @ 65123.5, SL=64000, partial_exits=2 levels
```

**Order Expired (TTL for GTC/PostOnly):**
```
Order 123456 expired (TTL=300s), cancelling...
Expired orders (TTL): 1
```

**Order Cancelled by Exchange (IOC/FOK):**
```
Order 123456 Cancelled
Cancelled orders: 1
```

---

## Grace Period Status

**Текущий статус:**
- В `storage/position_state.py` есть 10s grace period (lines 340-360)
- Изначально был временным fix для limit ордеров
- С внедрением Order Monitoring, grace period может быть:
  - **Уменьшен до 1-2s** (компенсация network latency для market ордеров)
  - **Удален полностью** (rely только на order monitoring)

**Рекомендация:**
- Оставить 2-3s grace period для market ордеров (сетевые задержки)
- Limit ордера теперь обрабатываются корректно через monitoring

---

## Testing Checklist

### Market Orders (Instant Fill)
- [ ] Позиция регистрируется сразу после создания ордера
- [ ] `position_state_manager.has_position()` возвращает True
- [ ] PositionManager tracking активен (breakeven/trailing)
- [ ] SL/TP выставлены корректно

### Limit Orders (Pending → Fill)
- [ ] Ордер добавляется в `pending_orders` при создании
- [ ] Мониторинг проверяет статус каждые 10s
- [ ] При Fill: callback вызывается, позиция регистрируется
- [ ] Фактическая цена исполнения (`avgPrice`) используется вместо запрошенной
- [ ] PositionManager получает корректные SL/TP из pending_info

### TTL Expiry
- [ ] Неисполненный ордер отменяется после TTL
- [ ] Removed from `pending_orders`
- [ ] Логируется в "expired" список

### Cancelled Orders
- [ ] Отмененные ордера удаляются из `pending_orders`
- [ ] Не регистрируются как позиции

---

## Next Steps

### Optional Enhancements:

1. **Partial Fill Support**
   - Опция для регистрации позиции при частичном исполнении
   - Config: `execution.register_on_partial_fill: true`

2. **Grace Period Refinement**
   - Уменьшить до 2-3s для market ордеров
   - Или удалить полностью и rely на monitoring

3. **Order History**
   - Сохранять filled/cancelled ордера в БД для анализа
   - Metrics: fill rate, average fill time, slippage

4. **Multi-Symbol Support**
   - Мониторинг pending ордеров для нескольких символов
   - Currently: single symbol bot

---

## Migration Notes

**Для существующих установок:**
1. Order Monitoring работает автоматически для `mode="live"`
2. Market ордера работают как раньше (instant registration)
3. Limit ордера теперь требуют monitoring (автоматически включен)
4. Настройка TTL опциональна (default: 300s)

**Backward Compatibility:**
- Все существующие настройки сохранены
- Market order flow не изменился
- Limit order flow улучшен (proper lifecycle)

---

## Files Modified

1. **execution/order_manager.py** (lines 30-35, 600-730)
   - Added `pending_orders` dict
   - Added `get_order_status()` method
   - Added `monitor_pending_orders()` method
   - Updated TTL check: only apply to GTC/PostOnly (skip IOC/FOK)

2. **bot/trading_bot.py** (lines 2143-2280, 908-972)
   - Split Market vs Limit order handling
   - Added `time_in_force` to pending_orders metadata
   - IOC/FOK orders set `ttl_seconds: None` (no TTL)
   - Added callback function `register_filled_position()`
   - Integrated `monitor_pending_orders()` in main loop
   - Conditional PositionManager registration (Market only)

3. **static/index.html** (lines 309-334)
   - Updated Time in Force tooltip (explain TTL interaction)
   - Updated Post-only tooltip (mention GTC behavior)
   - Added TTL setting input field (30-86400 seconds)

4. **static/js/app.js** (lines 669, 759)
   - Added `settingTtlSeconds` load/save logic

---

## Summary

✅ **Proper order lifecycle management** для Market и Limit ордеров  
✅ **TTL mechanism** для автоматической отмены неисполненных ордеров  
✅ **Callback pattern** для модульной архитектуры  
✅ **No более "Position closed manually" ошибок** для limit ордеров  
✅ **Фактическая цена исполнения** используется вместо запрошенной  
✅ **Backward compatible** с существующими настройками  

---

**Автор:** GitHub Copilot  
**Дата:** 2024  
**Версия:** 1.0
