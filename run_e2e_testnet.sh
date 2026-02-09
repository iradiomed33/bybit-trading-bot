#!/bin/bash
# E2E Testnet Test Runner для Linux/Mac
# 
# Этот скрипт запускает полный цикл E2E тестов на Bybit testnet
# ТРЕБУЕТ: BYBIT_API_KEY и BYBIT_API_SECRET в .env файле

set -e  # Выход при ошибке

echo "========================================"
echo "E2E TESTNET INTEGRATION TEST"
echo "========================================"
echo ""

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "[ERROR] Файл .env не найден!"
    echo ""
    echo "Создайте .env файл со следующим содержимым:"
    echo "BYBIT_API_KEY=your_testnet_api_key"
    echo "BYBIT_API_SECRET=your_testnet_api_secret"
    echo ""
    exit 1
fi

# Активация виртуального окружения (если есть)
if [ -f .venv/bin/activate ]; then
    echo "Активация виртуального окружения..."
    source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
    echo "Активация виртуального окружения..."
    source venv/bin/activate
else
    echo "[WARNING] Виртуальное окружение не найдено"
fi

echo ""
echo "[INFO] Проверка API ключей..."
if ! python check_api_keys.py; then
    echo ""
    echo "[ERROR] API ключи не работают!"
    echo "Прочитайте SETUP_API_KEYS.md для настройки."
    exit 1
fi

echo ""
echo "[INFO] Запуск E2E тестов на testnet..."
echo "[WARNING] Эти тесты создают РЕАЛЬНЫЕ ордера на Bybit testnet!"
echo ""

# Установка флага для запуска E2E тестов
export RUN_TESTNET_E2E=1

# Запуск тестов с подробным выводом
if pytest tests/e2e/test_full_trade_cycle_testnet.py -v -s --tb=short; then
    echo ""
    echo "========================================"
    echo "[SUCCESS] Все E2E тесты passed!"
    echo "========================================"
    exit 0
else
    echo ""
    echo "========================================"
    echo "[FAILED] Некоторые тесты не прошли"
    echo "========================================"
    echo ""
    echo "Проверьте:"
    echo "1. API ключи в .env файле корректны"
    echo "2. Баланс на testnet аккаунте"
    echo "3. Интернет соединение"
    echo "4. Логи выше для детальной диагностики"
    exit 1
fi
