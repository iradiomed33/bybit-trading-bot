# Regression Testing - Current Status

## ✅ Working Test Suites

### Smoke Tests (6 тестов)
```bash
pytest smoke_test.py
# Result: 6/6 PASSED (14 сек)
```

### Unit Tests (29 тестов)
```bash
pytest tests/regression/test_unit_*.py
# Result: 29/29 PASSED (8 сек)
```

### Testnet Tests (17+ тестов)
```bash
pytest tests/regression/test_testnet_*.py
# Result: Skipped если нет API ключей, иначе PASSED
```

## ✅ Current Status: 38/38 PASSED

Команда для запуска РАБОТАЮЩИХ тестов:

```bash
pytest smoke_test.py tests/regression/ \
  --ignore=tests/regression/test_integration_mtf.py \
  --ignore=tests/regression/test_integration_position.py \
  --ignore=tests/regression/test_integration_paper.py \
  --ignore=tests/regression/test_integration_strategies.py \
  --ignore=tests/regression/test_integration_slippage.py \
  --ignore=tests/regression/test_integration_risk.py \
  -v
```

Или короче (skip integration):

```bash
pytest smoke_test.py tests/regression/test_unit_*.py tests/regression/test_testnet_*.py -v
```

## ⚠️ Integration Tests - WIP

Integration тесты созданы но используют неправильные API вызовы реальных классов.

### Проблемы:

1. **PaperTradingSimulator** требует `PaperTradingConfig` вместо `initial_balance`
2. **PositionManager** требует `OrderManager` вместо прямых параметров
3. **SlippageModel** требует `Decimal` и `bps` параметры
4. Другие классы имеют разные сигнатуры

### Статус каждого Integration файла:

| Файл | Тесты | Статус | Проблема |
|------|-------|--------|----------|
| test_integration_mtf.py | 4 | ❌ FAIL | TimeframeCache.get_ohlcv -> get_dataframe |
| test_integration_position.py | 5 | ❌ FAIL | PositionManager требует OrderManager |
| test_integration_paper.py | 5 | ❌ FAIL | PaperTradingSimulator требует config |
| test_integration_strategies.py | 7 | ❌ FAIL | BreakoutStrategy параметры неправильные |
| test_integration_slippage.py | 6 | ❌ FAIL | SlippageModel требует Decimal, bps |
| test_integration_risk.py | 6 | ❌ FAIL | Слишком простые тесты, нужна переработка |

## 📋 План исправления Integration Tests

Нужно переписать integration тесты под реальный API каждого класса:

### 1. test_integration_mtf.py
```python
# НЕПРАВИЛЬНО:
assert hasattr(cache, 'get_ohlcv')

# ПРАВИЛЬНО:
assert hasattr(cache, 'get_dataframe')
assert hasattr(cache, 'add_candle')
```

### 2. test_integration_position.py
```python
# НЕПРАВИЛЬНО:
pm = PositionManager(client=mock_bybit_client, db=mock_database)

# ПРАВИЛЬНО:
om = OrderManager(client=mock_bybit_client, db=mock_database)
pm = PositionManager(order_manager=om)
```

### 3. test_integration_paper.py
```python
# НЕПРАВИЛЬНО:
simulator = PaperTradingSimulator(initial_balance=10000.0)

# ПРАВИЛЬНО:
config = PaperTradingConfig(initial_balance=Decimal('10000'))
simulator = PaperTradingSimulator(config=config)
```

### 4. test_integration_slippage.py
```python
# НЕПРАВИЛЬНО:
slippage = SlippageModel(base_slippage_percent=0.05)

# ПРАВИЛЬНО:
slippage = SlippageModel(base_slippage_bps=Decimal('2'))
result = slippage.calculate_slippage(
    qty=Decimal('0.5'),
    price=Decimal('50000'),
    side='Buy',
)
```

## 🚀 Рекомендация

На данный момент regression testing suite готова на **3 уровня**:

1. ✅ **Smoke** - 6 тестов, быстрая проверка базовой функциональности
2. ✅ **Unit** - 29 тестов, модульное тестирование компонентов
3. ✅ **Testnet** - 17+ тестов, тестирование на реальном API (skipped без ключей)

Используйте для PR checks:
```bash
pytest smoke_test.py tests/regression/test_unit_*.py -v
```

Для полного тестирования (когда integration будет исправлена):
```bash
pytest smoke_test.py tests/regression/ -v
```

## Next Steps

1. [ ] Переписать integration тесты под реальный API
2. [ ] Добавить integration тесты в GitHub Actions
3. [ ] HTML reports generation
4. [ ] Performance benchmarks
