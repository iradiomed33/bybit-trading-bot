# Нормализация tick/step через InstrumentsManager

## Проблема

При создании ордеров необходимо округлять цену и количество согласно правилам биржи:
- **tickSize** - минимальный шаг цены (например, 0.01 для BTCUSDT)
- **qtyStep** - минимальный шаг количества (например, 0.001 для BTCUSDT)

**Было:**
```python
# ❌ Хардкод - неправильно для всех символов!
position_qty_rounded = qty.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
```

**Проблемы:**
- Разные символы имеют разные tickSize/qtyStep
- Хардкод не учитывает реальные параметры биржи
- Биржа отклоняет ордера с ошибкой "invalid price/qty step"

## Решение: Модуль normalization.py

Центральное место для всех операций округления, использующее реальные параметры из `InstrumentsManager`.

### Основные функции

#### 1. round_price()

Округляет цену согласно tickSize инструмента.

```python
from exchange.normalization import round_price

# Автоматически использует tickSize=0.01 для BTCUSDT
price = round_price(instruments_manager, "BTCUSDT", 42123.456)
# Result: Decimal("42123.46")

# Автоматически использует tickSize=0.5 для ETHUSDT (пример)
price = round_price(instruments_manager, "ETHUSDT", 2345.234)
# Result: Decimal("2345.0")
```

**Параметры:**
- `instruments_manager` - InstrumentsManager instance
- `symbol` - торговая пара (BTCUSDT, ETHUSDT и т.д.)
- `price` - цена для округления (float или Decimal)

**Возвращает:** Decimal - округленная цена

**Raises:** ValueError если инструмент не найден

#### 2. round_qty()

Округляет количество согласно qtyStep инструмента.

```python
from exchange.normalization import round_qty

# Автоматически использует qtyStep=0.001 для BTCUSDT
qty = round_qty(instruments_manager, "BTCUSDT", 0.123456)
# Result: Decimal("0.123")

# Автоматически использует qtyStep=0.01 для ETHUSDT (пример)
qty = round_qty(instruments_manager, "ETHUSDT", 1.234567)
# Result: Decimal("1.23")
```

**Параметры:**
- `instruments_manager` - InstrumentsManager instance
- `symbol` - торговая пара
- `qty` - количество для округления (float или Decimal)

**Возвращает:** Decimal - округленное количество (ROUND_DOWN для qty)

**Raises:** ValueError если инструмент не найден

#### 3. validate_order()

Проверяет ордер согласно требованиям биржи.

```python
from exchange.normalization import validate_order

is_valid, error_msg = validate_order(
    instruments_manager,
    "BTCUSDT",
    price=42000,
    qty=0.001
)

if not is_valid:
    print(f"Order invalid: {error_msg}")
```

**Проверки:**
- minOrderQty - минимальное количество
- maxOrderQty - максимальное количество
- minNotional - минимальная сумма (qty * price)

#### 4. normalize_and_validate()

Полная нормализация и валидация ордера.

```python
from exchange.normalization import normalize_and_validate

normalized_price, normalized_qty, error_msg = normalize_and_validate(
    instruments_manager,
    "BTCUSDT",
    price=42123.456,
    qty=0.123456
)

if error_msg:
    print(f"Error: {error_msg}")
else:
    print(f"Price: {normalized_price}, Qty: {normalized_qty}")
```

**Этапы:**
1. Округление price по tickSize
2. Округление qty по qtyStep
3. Валидация против минималов

## Интеграция в компоненты

### VolatilityPositionSizer

**Использование:**

```python
from risk.volatility_position_sizer import VolatilityPositionSizer

# При создании передаём instruments_manager
sizer = VolatilityPositionSizer(
    config=config,
    instruments_manager=instruments_manager,  # ✅
)

# При расчёте передаём symbol
qty, details = sizer.calculate_position_size(
    account_balance=Decimal("10000"),
    entry_price=Decimal("42000"),
    atr=Decimal("500"),
    symbol="BTCUSDT",  # ✅
)

# qty автоматически округлён по qtyStep символа BTCUSDT
```

**Внутренняя логика:**

```python
if self.instruments_manager and symbol:
    # ✅ Используем реальный qtyStep
    position_qty_rounded = round_qty(
        self.instruments_manager,
        symbol,
        position_qty_constrained
    )
else:
    # Fallback (deprecated)
    position_qty_rounded = position_qty_constrained.quantize(...)
```

### TradingBot

**Инициализация:**

```python
# InstrumentsManager создаётся при старте
self.instruments_manager = InstrumentsManager(rest_client, category="linear")
self.instruments_manager.load_instruments()

# Передаётся в VolatilityPositionSizer
self.volatility_position_sizer = VolatilityPositionSizer(
    config,
    instruments_manager=self.instruments_manager,
)
```

**Использование при создании ордера:**

```python
# 1. Расчёт qty с учётом округления
qty_vol, _ = self.volatility_position_sizer.calculate_position_size(
    account=account_balance,
    entry_price=entry_price,
    atr=atr,
    symbol=self.symbol,  # ✅
)

# 2. Нормализация перед отправкой
from exchange.instruments import normalize_order

normalized_price, normalized_qty, is_valid, message = normalize_order(
    self.instruments_manager,
    self.symbol,
    signal["entry_price"],
    qty_vol,
)

# 3. Создание ордера
if is_valid:
    result = self.order_manager.create_order(
        category="linear",
        symbol=self.symbol,
        price=float(normalized_price),
        qty=float(normalized_qty),
        ...
    )
```

## Примеры

### Пример 1: Базовое округление

```python
from exchange.instruments import InstrumentsManager
from exchange.normalization import round_price, round_qty

# Инициализация
instruments_manager = InstrumentsManager(rest_client, category="linear")
instruments_manager.load_instruments()

# Округление цены
price = round_price(instruments_manager, "BTCUSDT", 42123.456)
print(price)  # Decimal("42123.46") для tickSize=0.01

# Округление количества
qty = round_qty(instruments_manager, "BTCUSDT", 0.123456)
print(qty)  # Decimal("0.123") для qtyStep=0.001
```

### Пример 2: Валидация ордера

```python
from exchange.normalization import normalize_and_validate

price, qty, error = normalize_and_validate(
    instruments_manager,
    "BTCUSDT",
    price=42000,
    qty=0.0005  # Меньше minOrderQty
)

if error:
    print(error)  # "Qty 0.0005 < minOrderQty 0.001 for BTCUSDT"
```

### Пример 3: Использование в стратегии

```python
class MyStrategy:
    def __init__(self, instruments_manager):
        self.instruments_manager = instruments_manager
    
    def calculate_order(self, symbol, price, qty):
        # Округляем и валидируем
        norm_price, norm_qty, error = normalize_and_validate(
            self.instruments_manager,
            symbol,
            price,
            qty
        )
        
        if error:
            raise ValueError(f"Invalid order: {error}")
        
        return {
            "symbol": symbol,
            "price": float(norm_price),
            "qty": float(norm_qty),
        }
```

## Преимущества

1. **Точность** - используются реальные tickSize/qtyStep из API биржи
2. **Единообразие** - одно место для всех округлений
3. **Безопасность** - гарантированно нет ошибок "invalid step"
4. **Автоматизация** - работает для любого символа
5. **Простота** - простой API для разработчиков
6. **Обратная совместимость** - fallback для legacy кода

## Ошибки и их решение

### ValueError: Instrument not found

```python
# ❌ Ошибка
qty = round_qty(instruments_manager, "UNKNOWN", 1.5)
# ValueError: Failed to normalize qty for UNKNOWN - instrument not found
```

**Решение:**
1. Проверьте что `instruments_manager.load_instruments()` вызван
2. Проверьте что символ существует на бирже
3. Используйте `instruments_manager.get_instrument(symbol)` для проверки

### ValueError: InstrumentsManager is None

```python
# ❌ Ошибка
qty = round_qty(None, "BTCUSDT", 1.5)
# ValueError: InstrumentsManager is None - cannot normalize qty
```

**Решение:**
Передайте корректный `InstrumentsManager` instance:
```python
instruments_manager = InstrumentsManager(rest_client)
instruments_manager.load_instruments()
qty = round_qty(instruments_manager, "BTCUSDT", 1.5)
```

## API Reference

### round_price(instruments_manager, symbol, price)

Округляет цену согласно tickSize.

**Args:**
- `instruments_manager` (InstrumentsManager) - manager instance
- `symbol` (str) - торговая пара
- `price` (float | Decimal) - цена для округления

**Returns:** Decimal

**Raises:** ValueError

### round_qty(instruments_manager, symbol, qty)

Округляет количество согласно qtyStep.

**Args:**
- `instruments_manager` (InstrumentsManager) - manager instance
- `symbol` (str) - торговая пара
- `qty` (float | Decimal) - количество для округления

**Returns:** Decimal (ROUND_DOWN)

**Raises:** ValueError

### validate_order(instruments_manager, symbol, price, qty)

Проверяет ордер согласно требованиям биржи.

**Args:**
- `instruments_manager` (InstrumentsManager) - manager instance
- `symbol` (str) - торговая пара
- `price` (float | Decimal) - цена ордера
- `qty` (float | Decimal) - количество

**Returns:** Tuple[bool, str] - (is_valid, error_message)

### normalize_and_validate(instruments_manager, symbol, price, qty)

Полная нормализация и валидация.

**Args:**
- `instruments_manager` (InstrumentsManager) - manager instance
- `symbol` (str) - торговая пара
- `price` (float | Decimal) - цена ордера
- `qty` (float | Decimal) - количество

**Returns:** Tuple[Optional[Decimal], Optional[Decimal], str]
- (normalized_price, normalized_qty, error_message)

## Миграция legacy кода

### До

```python
# ❌ Хардкод
from decimal import Decimal, ROUND_HALF_UP

qty_rounded = qty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
price_rounded = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### После

```python
# ✅ Используем реальные параметры биржи
from exchange.normalization import round_price, round_qty

qty_rounded = round_qty(instruments_manager, symbol, qty)
price_rounded = round_price(instruments_manager, symbol, price)
```

## Тестирование

```bash
# Smoke test
python test_normalization_smoke.py

# Полный набор тестов
python -m pytest tests/test_instruments.py -v
```

## Заключение

Модуль `exchange/normalization.py` предоставляет унифицированный способ округления цен и количеств согласно реальным параметрам биржи. Использование этого модуля гарантирует, что биржа не будет отклонять ордера с ошибками "invalid price/qty step".

**Ключевой принцип:** Всегда используйте реальные tickSize/qtyStep из InstrumentsManager, а не хардкод значений.
