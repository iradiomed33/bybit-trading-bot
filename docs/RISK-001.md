# RISK-001: Risk-per-trade Management

**Status**: ✅ COMPLETED  
**Tests**: 21 comprehensive tests  
**Coverage**: Risk calculation, position sizing, all limits enforcement

## Описание

Система управления риском на уровне каждой торговли:
- Расчет risk_per_trade: `risk_usd = equity * risk_pct`
- Position sizing от stop-distance: `qty = risk_usd / (entry_price - stop_loss_price)`
- Ограничения: max_leverage, max_notional, max_exposure
- Защита от убытков: daily_loss_limit

DoD:
- ✅ Любая сделка не превышает risk-лимит в USD
- ✅ Reject с понятной причиной при превышении

## Архитектура

### RiskLimits - конфигурация лимитов

```python
from risk.risk_manager import RiskLimits, RiskManager

limits = RiskLimits(
    risk_percent_per_trade=Decimal("1"),        # 1% на сделку
    max_leverage=Decimal("10"),                 # Max 10x
    max_notional_usd=Decimal("100000"),         # Max $100k notional
    max_open_exposure_usd=Decimal("50000"),     # Max $50k exposure
    max_daily_loss_percent=Decimal("5"),        # Max 5% daily loss
    max_total_open_positions=5,                 # Max 5 позиций
    min_stop_distance_percent=Decimal("1"),     # Min 1% stop
)

# Валидировать
valid, msg = limits.validate()
```

### RiskManager - менеджер риска

```python
manager = RiskManager(limits=limits)

# Обновить состояние счета
manager.update_account_state(
    equity=Decimal("10000"),
    cash=Decimal("10000"),
    open_positions={"BTCUSDT": Decimal("0.5")},
    daily_loss=Decimal("100"),
)

# Расчитать рекомендуемый размер позиции
analysis = manager.calculate_position_size(
    entry_price=Decimal("50000"),
    stop_loss_price=Decimal("45000"),
)

# analysis.risk_usd = 100 USD (1% от 10000)
# analysis.position_qty = 0.02 (100 / 5000)
# analysis.notional_value = 1000 (0.02 * 50000)
# analysis.stop_distance_pct = 10%

# Валидировать ордер перед submission
is_valid, reason = manager.validate_order(
    symbol="BTCUSDT",
    qty=Decimal("0.02"),
    entry_price=Decimal("50000"),
    stop_loss_price=Decimal("45000"),
)

# Получить рекомендации
info = manager.get_recommended_order_info(
    entry_price=Decimal("50000"),
    stop_loss_price=Decimal("45000"),
)

# Получить summary счета
summary = manager.get_account_summary()
```

## Формулы

### 1. Risk per Trade
```
risk_usd = equity * risk_percent / 100
```
**Пример**: 10000 equity * 1% = 100 USD risk per trade

### 2. Position Sizing
```
stop_distance = entry_price - stop_loss_price
qty = risk_usd / stop_distance
```
**Пример**:
- Entry: 50000, SL: 45000 → stop_distance = 5000
- risk_usd = 100
- qty = 100 / 5000 = 0.02 BTC

### 3. Notional Value
```
notional = qty * entry_price
```
**Пример**: 0.02 * 50000 = 1000 USD

### 4. Required Leverage
```
leverage = notional / cash
```
**Пример**: 1000 / 10000 = 0.1x

## Примеры

### Пример 1: Базовый risk расчет

```python
from risk.risk_manager import RiskManager, RiskLimits
from decimal import Decimal

manager = RiskManager(
    limits=RiskLimits(risk_percent_per_trade=Decimal("1"))
)
manager.update_account_state(
    equity=Decimal("10000"),
    cash=Decimal("10000"),
)

# Вход @ 50000, SL @ 45000
analysis = manager.calculate_position_size(
    entry_price=Decimal("50000"),
    stop_loss_price=Decimal("45000"),
)

print(f"Risk: ${analysis.risk_usd}")           # 100
print(f"Qty: {analysis.position_qty}")         # 0.02
print(f"Stop distance: {analysis.stop_distance_pct}%")  # 10%
```

### Пример 2: Validation перед ордером

```python
is_valid, reason = manager.validate_order(
    symbol="BTCUSDT",
    qty=Decimal("0.02"),
    entry_price=Decimal("50000"),
    stop_loss_price=Decimal("45000"),
)

if is_valid:
    print("✓ Order approved")
    submit_order(...)
else:
    print(f"✗ Order rejected: {reason}")
    # Пример: "Leverage 1.5x превышает max 1.0x"
```

### Пример 3: Превышение лимита exposure

```python
limits = RiskLimits(max_open_exposure_usd=Decimal("50000"))
manager = RiskManager(limits=limits)
manager.update_account_state(
    equity=Decimal("100000"),
    cash=Decimal("100000"),
    open_positions={"BTCUSDT": Decimal("0.5"), "ETHUSDT": Decimal("10")},
    # Total exposure ~50000, уже на лимите
)

# Пытаемся открыть еще
is_valid, reason = manager.validate_order(
    symbol="LTCUSDT",
    qty=Decimal("1000"),
    entry_price=Decimal("100"),
    # Notional = 100000 (превышает лимит)
)

# Результат: False
# Reason: "Total exposure 150000.00 USD превышает max 50000.00 USD"
```

## Лимиты и их проверка

| Лимит | Дефолт | Проверка | Сообщение об ошибке |
|-------|--------|---------|---------------------|
| risk_percent | 1% | qty > recommended | "Qty превышает recommended" |
| max_leverage | 10x | notional/cash > limit | "Required leverage превышает max" |
| max_notional | $100k | qty * price > limit | "Notional превышает max" |
| max_exposure | $50k | sum(all_notional) > limit | "Total exposure превышает max" |
| max_positions | 5 | len(open) >= limit | "Max open positions уже открыто" |
| daily_loss | 5% | daily_pnl < limit | "Daily loss limit достигнут" |
| min_stop_distance | 1% | (entry-sl)/entry < min | "Stop distance меньше минимума" |

## Тесты (21 тест)

### RiskLimits (2)
- ✅ Default values correct
- ✅ Validation works

### Position Size Calculation (4)
- ✅ Basic size calculation
- ✅ Stop distance percentage
- ✅ Invalid stop above entry
- ✅ Min stop distance enforcement

### Order Validation (3)
- ✅ Valid order passes
- ✅ Zero qty rejected
- ✅ Negative price rejected

### Limits Enforcement (8)
- ✅ Max notional exceeded
- ✅ Within notional limit
- ✅ Single position within exposure
- ✅ Multiple positions exceed exposure
- ✅ Max positions limit
- ✅ Leverage calculation
- ✅ Daily loss limit exceeded

### Recommendations (2)
- ✅ Recommended order info
- ✅ Recommended qty exceeds notional

### Account Summary (1)
- ✅ Account summary correct

## Интеграция

### Текущая реализация
- ✅ RiskManager класс готов
- ✅ Все лимиты работают
- ✅ Валидация ордеров работает
- ✅ Рекомендации генерируются

### Следующие этапы интеграции
1. Интегрировать в OrderManager для pre-validation
2. Интегрировать в TradingBot для check перед signal_processing
3. Добавить risk/equity reporting в API
4. Добавить risk dashboard в UI

## Файлы

- ✅ risk/risk_manager.py (350+ lines)
- ✅ tests/test_risk_manager.py (420+ lines)
- ✅ docs/RISK-001.md (this file)

## DoD Верификация

✅ **DoD #1**: Любая сделка не превышает risk-лимит в USD
- Проверено: `validate_order()` отклоняет если qty > recommended по risk

✅ **DoD #2**: Reject с понятной причиной при превышении
- Примеры сообщений:
  - "Leverage 25.0x превышает max 2.0x"
  - "Notional 250000.00 USD превышает max 100000.00 USD"
  - "Total exposure 150000.00 USD превышает max 50000.00 USD"
  - "Max open positions 5 уже открыто"
  - "Daily loss limit достигнут: 600.00 USD (max 5% = 500.00 USD)"

## Статистика

```
Test Results:
✅ 21 RISK-001 tests (test_risk_manager.py)
✅ 82 existing tests (no regressions)
✅ 103 total tests PASSED

Coverage:
- Risk calculations ✓
- Position sizing ✓
- All limits (7 types) ✓
- Edge cases ✓
- Error messages ✓
```

## Next Steps

1. **RISK-002**: Correlation-based drawdown protection
2. **RISK-003**: Kelly criterion sizing (optimal position size)
3. **RISK-004**: Heat map risk visualization (equity curve analysis)
4. **Интеграция**: OrderManager validation pre-hook
