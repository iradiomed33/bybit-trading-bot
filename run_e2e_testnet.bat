@echo off
REM E2E Testnet Test Runner для Windows
REM 
REM Этот скрипт запускает полный цикл E2E тестов на Bybit testnet
REM ТРЕБУЕТ: BYBIT_API_KEY и BYBIT_API_SECRET в .env файле

echo ========================================
echo E2E TESTNET INTEGRATION TEST
echo ========================================
echo.

REM Проверка наличия .env файла
if not exist .env (
    echo [ERROR] Файл .env не найден!
    echo.
    echo Создайте .env файл со следующим содержимым:
    echo BYBIT_API_KEY=your_testnet_api_key
    echo BYBIT_API_SECRET=your_testnet_api_secret
    echo.
    echo Подробнее: см. SETUP_API_KEYS.md
    pause
    exit /b 1
)

REM Активация виртуального окружения (если есть)
if exist .venv\Scripts\activate.bat (
    echo Активация виртуального окружения...
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo Активация виртуального окружения...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] Виртуальное окружение не найдено
)

echo.
echo [INFO] Проверка API ключей...
python check_api_keys.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] API ключи не работают!
    echo Прочитайте SETUP_API_KEYS.md для настройки.
    pause
    exit /b 1
)

echo.
echo [INFO] Запуск E2E тестов на testnet...
echo [WARNING] Эти тесты создают РЕАЛЬНЫЕ ордера на Bybit testnet!
echo.

REM Установка флага для запуска E2E тестов
set RUN_TESTNET_E2E=1

REM Запуск тестов с подробным выводом
pytest tests\e2e\test_full_trade_cycle_testnet.py -v -s --tb=short

REM Проверка результата
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo [SUCCESS] Все E2E тесты passed!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo [FAILED] Некоторые тесты не прошли
    echo ========================================
    echo.
    echo Проверьте:
    echo 1. API ключи в .env файле корректны
    echo 2. Баланс на testnet аккаунте
    echo 3. Интернет соединение
    echo 4. Логи выше для детальной диагностики
)

echo.
pause
