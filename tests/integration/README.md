# Integration Tests для Bybit Trading Bot (Testnet)

Эти тесты проверяют работу бота на реальном testnet Bybit.

## Настройка

### 1. Получить Testnet API ключи

1. Зарегистрироваться на https://testnet.bybit.com
2. Пополнить testnet аккаунт (бесплатно)
3. Создать API ключи в настройках

### 2. Настроить environment variables

Создайте файл `.env` в корне проекта:

```bash
cp .env.example .env
```

Заполните:
```bash
BYBIT_TESTNET_API_KEY=your_testnet_api_key_here
BYBIT_TESTNET_API_SECRET=your_testnet_secret_here
BYBIT_TESTNET_ENABLED=true
```

### 3. Установить зависимости

```bash
pip install pytest pytest-asyncio python-dotenv
```

## Запуск тестов

### Все тесты

```bash
pytest tests/integration/ -v
```

### Конкретный сценарий

```bash
pytest tests/integration/test_01_startup_instruments.py -v
```

### С детальным выводом

```bash
pytest tests/integration/ -v -s
```

## Сценарии тестирования

### 1. test_01_startup_instruments.py
Проверяет старт бота, загрузку инструментов и WebSocket подключение.

### 2. test_02_order_fill_position.py
Проверяет размещение ордера, получение fill и обновление позиции.

### 3. test_03_sltp_management.py
Проверяет установку и отмену SL/TP через Trading Stop API.

### 4. test_04_cancel_all_orders.py
Проверяет создание и отмену всех ордеров.

### 5. test_05_kill_switch.py
Проверяет активацию kill-switch и закрытие всех позиций.

## Безопасность

- ✅ Тесты работают **только на testnet**
- ✅ Автоматически **skip без credentials**
- ✅ **Cleanup** после каждого теста
- ✅ Минимальные размеры позиций

## Troubleshooting

### Тесты пропускаются (skipped)

Убедитесь что:
1. `.env` файл создан
2. API ключи корректны
3. `BYBIT_TESTNET_ENABLED=true`

### Insufficient balance

Пополните testnet аккаунт на https://testnet.bybit.com

### Rate limit errors

Подождите 1-2 минуты между запусками тестов.

## CI/CD

В CI окружении без testnet credentials тесты автоматически пропускаются.

Для включения в CI:
1. Добавить secrets в GitHub:
   - `BYBIT_TESTNET_API_KEY`
   - `BYBIT_TESTNET_API_SECRET`
2. Настроить workflow для установки env переменных
