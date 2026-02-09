# 🔑 Настройка API ключей для E2E тестов

## Проблема

Тесты падают с ошибкой аутентификации:
```
Error sign, please check your signature generation algorithm
```

Это значит что API ключи от Bybit testnet не установлены или неверные.

## Решение

### Шаг 1: Получите API ключи от Bybit Testnet

1. **Регистрация на testnet:**
   - Перейдите на https://testnet.bybit.com/
   - Зарегистрируйтесь (можно использовать тот же email что и на основном сайте)

2. **Пополните тестовый баланс:**
   - Перейдите в https://testnet.bybit.com/app/user/assets
   - Нажмите "Get testnet assets" или используйте faucet
   - Получите тестовый USDT (обычно дают 10,000 USDT)

3. **Создайте API ключ:**
   - Перейдите в https://testnet.bybit.com/app/user/api-management
   - Нажмите "Create New Key"
   - **Важно:** Установите следующие права:
     - ✅ Read-Write (для торговли)
     - ✅ Contract Trade (для futures)
   - Скопируйте API Key и API Secret
   - **ВАЖНО:** API Secret показывается только один раз!

### Шаг 2: Создайте .env файл

В **корне проекта** (c:\bybit-trading-bot\) создайте файл `.env` со следующим содержимым:

```bash
# Bybit Testnet API Keys
BYBIT_API_KEY=ваш_api_key_здесь
BYBIT_API_SECRET=ваш_api_secret_здесь
```

**Пример:**
```bash
BYBIT_API_KEY=fQ1QGUQCnAk6XgMzVm
BYBIT_API_SECRET=XyZ123AbC456DeF789
```

### Шаг 3: Проверьте что .env загружается

Убедитесь что у вас установлен пакет python-dotenv:

```powershell
pip install python-dotenv
```

Проверьте что ключи загружаются:

```powershell
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', os.getenv('BYBIT_API_KEY', 'NOT SET'))"
```

Должно вывести ваш API ключ.

### Шаг 4: Запустите тест снова

```powershell
$env:RUN_TESTNET_E2E="1"
pytest tests\e2e\test_full_trade_cycle_testnet.py -v -s
```

## Безопасность

⚠️ **ВАЖНЫЕ ПРАВИЛА:**

1. **НЕ коммитьте .env файл в Git!**
   - Файл `.env` уже добавлен в `.gitignore`
   - Никогда не публикуйте API ключи

2. **Используйте ТОЛЬКО testnet ключи!**
   - Никогда не используйте production ключи для тестов
   - Production и testnet - разные системы

3. **Ограничьте права API ключа:**
   - Разрешите только Contract Trade
   - Не давайте права на вывод средств (Withdraw)

4. **IP whitelist (опционально):**
   - В настройках API ключа можно указать разрешенные IP
   - Это дополнительная защита

## Пример правильного .env файла

```bash
# ===========================================
# BYBIT TESTNET API KEYS
# ===========================================
# ВАЖНО: Это ключи от TESTNET, не production!
# Получить: https://testnet.bybit.com/app/user/api-management
# ===========================================

BYBIT_API_KEY=your_testnet_api_key_here
BYBIT_API_SECRET=your_testnet_api_secret_here

# Опционально: явно указать что это testnet
BYBIT_TESTNET=true
```

## Альтернатива: Переменные окружения

Вместо .env файла можно установить переменные окружения напрямую:

### Windows PowerShell:
```powershell
$env:BYBIT_API_KEY="ваш_ключ"
$env:BYBIT_API_SECRET="ваш_секрет"
$env:RUN_TESTNET_E2E="1"

pytest tests\e2e\test_full_trade_cycle_testnet.py -v
```

### Linux/Mac:
```bash
export BYBIT_API_KEY="ваш_ключ"
export BYBIT_API_SECRET="ваш_секрет"
export RUN_TESTNET_E2E="1"

pytest tests/e2e/test_full_trade_cycle_testnet.py -v
```

## Проверка работы API ключей

Простой скрипт для проверки:

```python
import os
from dotenv import load_dotenv
from exchange.base_client import BybitRestClient
from exchange.account import AccountClient

# Загрузка .env
load_dotenv()

# Проверка что ключи загрузились
api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')

print(f"API Key: {api_key[:8]}...{api_key[-4:] if api_key else 'NOT SET'}")
print(f"API Secret: {'SET' if api_secret else 'NOT SET'}")

# Попытка получить баланс
try:
    client = AccountClient(api_key=api_key, api_secret=api_secret, testnet=True)
    positions = client.get_positions(symbol='BTCUSDT')
    
    if positions.get('retCode') == 0:
        print("✅ API ключи работают!")
        print(f"Позиций найдено: {len(positions.get('result', {}).get('list', []))}")
    else:
        print(f"❌ Ошибка: {positions.get('retMsg')}")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
```

Сохраните как `test_api_keys.py` и запустите:

```powershell
python test_api_keys.py
```

## Troubleshooting

### "Error sign" ошибка продолжается

1. Проверьте что скопировали ключи БЕЗ пробелов
2. Убедитесь что используете testnet ключи, не production
3. Проверьте что API ключ активен (не истек срок действия)
4. Попробуйте создать новый API ключ

### "Insufficient balance"

1. Пополните баланс через faucet: https://testnet.bybit.com/app/user/assets
2. Подождите несколько минут после пополнения

### "IP restricted"

1. Зайдите в настройки API ключа
2. Удалите IP whitelist или добавьте ваш текущий IP
3. Узнать ваш IP: https://api.ipify.org/

## Готово! 🎉

После настройки API ключей тест должен успешно пройти все этапы:

```
✓ test_00_preparation
✓ test_01_open_position
✓ test_02_set_sl_tp
✓ test_03_close_position
✓ test_04_cleanup
✓ test_05_verify_final_state
```
