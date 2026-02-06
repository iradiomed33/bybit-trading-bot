# Запуск Регресса: Инструкции

## Быстрый старт

### 1. Smoke-тесты (уже прошли ✅)
```bash
python smoke_test.py
# Результат: smoke_test_report.json
```

---

## 2. Unit-тесты (локально, быстро, ~2 мин)

### Установка зависимостей
```bash
pip install pytest pandas numpy
```

### Запуск
```bash
# Все unit-тесты
pytest tests/regression/test_unit_*.py -v

# Конкретный файл
pytest tests/regression/test_unit_indicators.py -v
pytest tests/regression/test_unit_api.py -v
pytest tests/regression/test_unit_position.py -v

# С покрытием
pytest tests/regression/test_unit_*.py -v --cov=data --cov=strategy --cov=execution
```

### Обзор unit-тестов
- `test_unit_indicators.py` — REG-A2, REG-A3, REG-A4 (индикаторы, RSI, фильтры)
- `test_unit_api.py` — REG-B1, REG-B3 (live-ветка, нормализация)
- `test_unit_position.py` — REG-C2, REG-D1, REG-D2 (SL/TP, kill switch, риск)

**Покрытие:** ~35 тестов | **Время:** ~2 мин

---

## 3. Integration-тесты (локально, медленнее, ~10 мин)

### Запуск
```bash
# Все integration-тесты
pytest tests/regression/test_integration_*.py -v

# С логами
pytest tests/regression/test_integration_*.py -v -s
```

### Обзор integration-тестов
- `test_integration_mtf.py` — REG-A1 (MTF загрузка)
- `test_integration_position.py` — REG-C1, REG-C3 (позиции, flip/add)
- `test_integration_paper.py` — REG-E1, REG-E2 (paper, backtest)
- `test_integration_strategies.py` — REG-STR (стратегии TTL/time stop)
- И другие...

**Покрытие:** ~25 тестов | **Время:** ~10 мин

---

## 4. Master регресс-скрипт (все уровни)

### Запуск полного регресса
```bash
# Все уровни (smoke + unit + integration)
python run_full_regression.py --level=all

# Только CI уровень (быстро)
python run_full_regression.py --level=ci

# Конкретный уровень
python run_full_regression.py --level=unit
python run_full_regression.py --level=smoke
python run_full_regression.py --level=integration

# С verbose выводом
python run_full_regression.py --level=all --verbose

# С HTML отчетом (опционально)
python run_full_regression.py --level=all --html
```

### Результаты
- `tests/regression/.reports/regression_final_report.json` — итоговый отчет
- `tests/regression/.reports/unit_report.json` — результаты unit-тестов
- `tests/regression/.reports/integration_report.json` — результаты integration-тестов
- `smoke_test_report.json` — результаты smoke-тестов

### Интерпретация exit code
```bash
0 = ✓ Успех (готово к релизу)
1 = ✗ Ошибка (требуется исправление)
```

---

## 5. Testnet-тесты (требуют API ключи)

### Подготовка
```bash
# Скопировать .env.example в .env
cp .env.example .env

# Заполнить BYBIT_API_KEY и BYBIT_API_SECRET в .env
BYBIT_API_KEY=your_testnet_key_here
BYBIT_API_SECRET=your_testnet_secret_here
```

### Запуск
```bash
# Только testnet
python run_full_regression.py --level=testnet --testnet

# Все уровни + testnet
python run_full_regression.py --level=all --testnet

# Конкретные testnet тесты
pytest tests/regression/test_testnet_*.py -v --testnet
```

**⚠️ Важно:** Testnet-тесты медленнее, используют реальный API, могут быть нестабильны. Используйте только перед релизом.

---

## 6. CI/CD интеграция (GitHub Actions)

### На каждый PR
```yaml
test.yml срабатывает:
- Smoke-тесты: ~15 сек
- Unit-тесты: ~2 мин
- Integration-тесты: ~10 мин
Итого: ~15 мин
```

### Nightly
```yaml
Запускается каждый день в 00:00 UTC:
- Все уровни: smoke + unit + integration
- Testnet-тесты (если есть ключи)
Итого: ~45 мин
```

### На релиз (manual)
```yaml
Запускается вручную:
- Все уровни: smoke + unit + integration + testnet
- Отправить отчет в Slack
- GO/NO-GO для релиза
Итого: ~1 час
```

---

## 7. Структура проекта

```
tests/regression/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_unit_*.py                 # Unit-тесты (35+)
├── test_integration_*.py          # Integration-тесты (25+)
├── test_testnet_*.py              # Testnet-тесты (11+)
├── fixtures/
│   ├── __init__.py
│   ├── data.py                    # OHLCV fixtures
│   ├── mocks.py                   # Mock объекты
│   └── ...
└── .reports/
    ├── unit_report.json
    ├── integration_report.json
    ├── testnet_report.json
    └── regression_final_report.json

smoke_test.py                       # Smoke-тесты (6)
run_full_regression.py              # Master скрипт
```

---

## 8. Отладка и помощь

### Запуск с debug логами
```bash
pytest tests/regression/test_unit_indicators.py -v -s --log-cli-level=DEBUG
```

### Запуск одного теста
```bash
pytest tests/regression/test_unit_indicators.py::TestREGA2_CanonicalColumns::test_feature_pipeline_required_columns -v
```

### Просмотр отчетов
```bash
# JSON отчет
cat tests/regression/.reports/regression_final_report.json | json_pp

# Дерево файлов
tree tests/regression -L 2
```

---

## 9. Критерии успеха (Release Gate)

✓ **Smoke:** 6/6 PASS  
✓ **Unit:** 35/35 PASS  
✓ **Integration:** 25/25 PASS  
✓ **Testnet:** 10/11 PASS (допуск 1 флейк)  

**ИТОГ:** GO TO RELEASE ✓

---

## 10. Распространённые проблемы

### "pytest: command not found"
```bash
pip install pytest
```

### "No module named 'data'"
```bash
# Убедиться что находишься в корне проекта
cd c:\bybit-trading-bot
python run_full_regression.py --level=unit
```

### Testnet-тесты падают с "auth error"
```bash
# Проверить API ключи в .env
echo $BYBIT_API_KEY
echo $BYBIT_API_SECRET
```

### Performance низкий
```bash
# Integration-тесты медленные, это нормально
# Они работают с БД, файлами, долгими расчетами
# Используйте --level=unit для быстрой проверки
```

---

## 11. Дальнейшее развитие

- [ ] Добавить больше integration-тестов (E2E)
- [ ] Настроить GitHub Actions workflows
- [ ] Добавить HTML отчеты с графиками
- [ ] Интеграция с Slack уведомлениями
- [ ] Performance бенчмарки
- [ ] Постоянное улучшение coverage
