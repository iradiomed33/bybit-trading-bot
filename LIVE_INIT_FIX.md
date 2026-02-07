# Исправление порядка инициализации компонентов TradingBot (P0)

## Проблема

При запуске бота в режиме `live` возникал `AttributeError`, потому что `StopLossTakeProfitManager` создавался раньше `OrderManager`, хотя зависит от него.

### Дефектный порядок (до исправления):
```python
# Строка 186: sl_tp_manager создаётся первым
self.sl_tp_manager = StopLossTakeProfitManager(self.order_manager, sl_tp_config)  # ❌ self.order_manager ещё не существует!

# Строка 322: order_manager создаётся позже
self.order_manager = OrderManager(rest_client, self.db)
```

Это приводило к `AttributeError: 'TradingBot' object has no attribute 'order_manager'`.

## Решение

Переупорядочены компоненты в методе `TradingBot.__init__()`:

### Правильный порядок (после исправления):

1. ✓ **Database** - создаётся в начале инициализации
2. ✓ **MarketDataClient** - создаётся после Database
3. ✓ **AccountClient** - создаётся после MarketDataClient
4. ✓ **BybitRestClient** - создаётся **один раз** для всех компонентов (в live режиме)
5. ✓ **InstrumentsManager** - использует BybitRestClient
6. ✓ **PositionStateManager** - использует AccountClient
7. ✓✓✓ **OrderManager** - теперь создаётся **ПЕРЕД** sl_tp_manager, использует BybitRestClient
8. ✓ **PositionManager** - использует OrderManager
9. ✓✓✓ **StopLossTakeProfitManager** - теперь может безопасно использовать `self.order_manager`
10. ✓ **KillSwitchManager** - использует BybitRestClient
11. ✓ **PositionSignalHandler** - не зависит от других менеджеров

### Дополнительные улучшения:

1. **Оптимизация**: `rest_client` теперь создаётся **один раз** в начале, а не три раза
2. **Убрано дублирование**: удалены повторные создания `order_manager` и `position_manager`
3. **Улучшена читаемость**: добавлены комментарии о зависимостях

## Изменённые файлы

- `bot/trading_bot.py` - исправлен порядок инициализации

## Тесты

1. **test_live_init_smoke.py** - smoke-test для проверки порядка инициализации
2. **test_live_initialization.py** - unit-test с моками для проверки инициализации

### Запуск тестов:

```bash
# Smoke test (быстрая проверка порядка)
python test_live_init_smoke.py

# Unit test (с моками)
python test_live_initialization.py
```

## Результат

✅ **Готово когда**: `mode=live` стартует без `AttributeError` и проходит smoke-run до подключения/первого тика.

Порядок инициализации теперь правильный:
- `order_manager` создаётся **ПЕРЕД** `sl_tp_manager`
- Проверено smoke-тестом: `test_live_init_smoke.py`

## Команда для верификации

```bash
# Проверить порядок инициализации
python test_live_init_smoke.py

# Проверить синтаксис
python -m py_compile bot/trading_bot.py
```

## Статус

✅ **ИСПРАВЛЕНО** - Порядок инициализации компонентов в live режиме теперь правильный.
