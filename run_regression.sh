#!/bin/bash

# Быстрый скрипт для запуска регресса на Windows (via PowerShell или WSL)
# Использование: bash run_regression.sh [smoke|unit|integration|ci|all]

LEVEL=${1:-ci}

echo "======================================================================"
echo "Bybit Trading Bot: Regression Suite"
echo "======================================================================"
echo "Level: $LEVEL"
echo ""

case $LEVEL in
  smoke)
    echo "▶ Запуск Smoke-тестов..."
    python smoke_test.py
    ;;
  unit)
    echo "▶ Запуск Unit-тестов..."
    pytest tests/regression/test_unit_*.py -v
    ;;
  integration)
    echo "▶ Запуск Integration-тестов..."
    pytest tests/regression/test_integration_*.py -v
    ;;
  ci)
    echo "▶ Запуск CI уровня (smoke + unit + integration)..."
    python run_full_regression.py --level=ci
    ;;
  all)
    echo "▶ Запуск всех тестов..."
    python run_full_regression.py --level=all
    ;;
  *)
    echo "Неизвестный уровень: $LEVEL"
    echo "Используйте: smoke|unit|integration|ci|all"
    exit 1
    ;;
esac

exit $?
