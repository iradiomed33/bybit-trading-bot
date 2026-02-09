# E2E Тесты на Bybit Testnet

## Описание

Полный цикл интеграционного E2E тестирования на реальном Bybit testnet. Эти тесты проверяют, что бот действительно может:

1. **Открыть позицию** через Market ордер
2. **Выставить SL/TP** через `/v5/position/trading-stop` API
3. **Закрыть позицию** через Market reduceOnly ордер
4. **Очистить состояние** (отменить ордера и стопы)

## Зачем это нужно?

- ✅ Проверка реальной работы с биржей, а не только mock'и
- ✅ Выявление проблем с API до продакшена
- ✅ Проверка корректности работы SL/TP через trading-stop
- ✅ Уверенность что cleanup работает правильно

## Требования

### 1. API ключи от Bybit Testnet

Создайте `.env` файл в корне проекта со следующими переменными:

```bash
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_api_secret
```

> **Важно:** Используйте ключи от **TESTNET**, а не production!

Получить тестовые ключи можно здесь:
- https://testnet.bybit.com/ (регистрация)
- https://testnet.bybit.com/app/user/api-management (создание API ключей)

### 2. Testnet аккаунт с балансом

Убедитесь что на вашем testnet аккаунте есть USDT. Получить тестовые средства можно через faucet:
- https://testnet.bybit.com/app/user/assets

### 3. Python окружение

Установите зависимости:

```bash
pip install -r requirements.txt
```

## Запуск тестов

### Флаг RUN_TESTNET_E2E

Для защиты от случайного запуска тестов (которые создают реальные ордера на бирже), 
необходимо установить переменную окружения `RUN_TESTNET_E2E=1`.

### Windows (PowerShell)

```powershell
# Установить переменную окружения
$env:RUN_TESTNET_E2E="1"

# Запустить тесты
pytest tests/e2e/test_full_trade_cycle_testnet.py -v -s
```

### Linux/Mac (Bash)

```bash
# Установить переменную и запустить тесты
RUN_TESTNET_E2E=1 pytest tests/e2e/test_full_trade_cycle_testnet.py -v -s
```

### Запуск через Python напрямую

```bash
RUN_TESTNET_E2E=1 python tests/e2e/test_full_trade_cycle_testnet.py
```

## Структура тестов

Тесты выполняются последовательно в следующем порядке:

### test_00_preparation
- Отменяет все активные ордера
- Закрывает существующие позиции
- Очищает trading stop

### test_01_open_position
- Получает текущую цену BTC/USDT
- Вычисляет минимальное qty согласно filters
- Открывает Market Buy позицию
- **Assertion:** позиция появилась на бирже, size > 0

### test_02_set_sl_tp
- Получает avgPrice открытой позиции
- Вычисляет SL (-2%) и TP (+3%)
- Выставляет SL/TP через `set_trading_stop`
- **Assertion:** на бирже появились stopLoss и takeProfit

### test_03_close_position
- Закрывает позицию через Market reduceOnly
- **Assertion:** размер позиции стал 0

### test_04_cleanup
- Очищает trading stop
- Отменяет все ордера

### test_05_verify_final_state
- Проверяет что позиция закрыта
- Проверяет что нет активных ордеров
- Проверяет что SL/TP очищены

## Параметры теста

### Настраиваемые параметры (в коде)

```python
TEST_SYMBOL = 'BTCUSDT'       # Тестовый символ
TEST_CATEGORY = 'linear'      # Категория (linear futures)
POSITION_INDEX = 0            # 0 = one-way mode
```

### SL/TP отступы

По умолчанию для Buy позиции:
- SL: -2% от avgPrice
- TP: +3% от avgPrice

Можно изменить в методе `test_02_set_sl_tp`.

## Ожидаемый результат

При успешном прохождении вы увидите:

```
=== STEP 0: Preparation ===
✓ Preparation complete

=== STEP 1: Open Position ===
Current price for BTCUSDT: 50000.0
Opening position: BTCUSDT qty=0.001
✓ Order created: 1234567890
✓ Position opened: size=0.001 side=Buy

=== STEP 2: Set SL/TP ===
Setting SL/TP: avgPrice=50000.0 SL=49000.0 TP=51500.0
✓ Trading stop set successfully
✓ SL/TP verified on exchange: SL=49000.0 TP=51500.0
✓ SL/TP values match expected

=== STEP 3: Close Position ===
Closing position: size=0.001 close_side=Sell
✓ Close order created: 9876543210
✓ Position closed successfully

=== STEP 4: Cleanup ===
✓ Cleanup complete

=== STEP 5: Verify Final State ===
✓ Final state verified - all clean

======================== 6 passed in 25.42s ========================
```

## Диагностика ошибок

### Ошибка: "BYBIT_API_KEY не установлен"

**Решение:** Создайте `.env` файл с API ключами или установите переменные окружения:

```bash
export BYBIT_API_KEY=your_key
export BYBIT_API_SECRET=your_secret
```

### Ошибка: "Failed to load instruments"

**Причины:**
- Нет интернета
- API Bybit недоступен
- Неверные API ключи

**Решение:** Проверьте подключение и ключи.

### Ошибка: "Failed to create order: insufficient balance"

**Причина:** Недостаточно средств на testnet аккаунте.

**Решение:** Пополните баланс через faucet: https://testnet.bybit.com/app/user/assets

### Ошибка: "Position size should be > 0, got 0"

**Причины:**
- Ордер не успел исполниться (таймаут)
- Недостаточная ликвидность на testnet

**Решение:** 
- Увеличьте `time.sleep()` после создания ордера
- Попробуйте другой символ (например, ETHUSDT)

### Ошибка: "Stop Loss should be set on position, got: "

**Причины:**
- Trading stop не успел примениться
- API вернул успех, но фактически не установил

**Решение:**
- Увеличьте `time.sleep()` после set_trading_stop
- Проверьте логи для детальной диагностики

## Логирование

Логи теста содержат подробную информацию о каждом шаге:

- Создание ордеров
- Текущие позиции
- Установка SL/TP
- Ответы API

Для максимальной детализации запускайте с флагом `-s`:

```bash
pytest tests/e2e/test_full_trade_cycle_testnet.py -v -s
```

## Безопасность

⚠️ **ВНИМАНИЕ:**

- Тесты создают **реальные ордера** на бирже (testnet)
- НЕ используйте production ключи!
- Флаг `RUN_TESTNET_E2E=1` обязателен для защиты от случайного запуска
- Тесты автоматически очищают позиции и ордера после себя

## Интеграция в CI/CD

Для запуска в CI pipeline добавьте в ваш `.gitlab-ci.yml` или `.github/workflows`:

```yaml
test_e2e_testnet:
  stage: test
  script:
    - export RUN_TESTNET_E2E=1
    - export BYBIT_API_KEY=$TESTNET_API_KEY
    - export BYBIT_API_SECRET=$TESTNET_API_SECRET
    - pytest tests/e2e/test_full_trade_cycle_testnet.py -v
  only:
    - main
    - develop
```

## Поддержка и вопросы

При возникновении проблем:

1. Проверьте логи теста
2. Убедитесь что API ключи корректны
3. Проверьте баланс на testnet
4. Откройте issue с логами

## Changelog

### v1.0.0 (2026-02-09)
- ✨ Первая версия E2E теста
- ✅ Полный цикл: открытие → SL/TP → закрытие → cleanup
- ✅ Проверка реального состояния на бирже
- ✅ Защита через RUN_TESTNET_E2E=1
- ✅ Подробная диагностика ошибок
