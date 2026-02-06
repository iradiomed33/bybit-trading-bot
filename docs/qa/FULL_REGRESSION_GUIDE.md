# Полный Regression Testing Guide

## Обзор

Regression testing suite включает **5 уровней** тестирования:

1. **Smoke** (~15 сек) - Критические проверки базовой функциональности
2. **Unit** (~10 сек) - Модульные тесты для компонентов
3. **Integration** (~30 сек) - Интеграционные тесты компонентов  
4. **Testnet** (~5 мин) - Тесты на реальном testnet API
5. **CI/CD** - Автоматизированные checks в GitHub Actions

---

## Quick Start

### 1. Запуск Smoke Tests (быстрая проверка)

```bash
pytest smoke_test.py -v
```

Результат: 6/6 PASSED за ~15 сек

```
test_smk_01_startup PASSED
test_smk_02_market_data PASSED
test_smk_03_feature_pipeline PASSED
test_smk_04_paper_mode PASSED
test_smk_05_testnet_api PASSED
test_smk_06_kill_switch PASSED
```

### 2. Запуск Unit Tests (полная валидация компонентов)

```bash
pytest tests/regression/test_unit_*.py -v
```

Результат: 29/29 PASSED за ~10 сек

**Охватываемые компоненты:**
- REG-A2: Feature Pipeline column names
- REG-A3: RSI indicator ranges
- REG-A4: Volume & Volatility filters
- REG-B1: Live order path
- REG-B3: Order normalization
- REG-C2: Stop Loss/TP management
- REG-D1: Kill switch mechanism
- REG-D2: Risk limits & position sizing

### 3. Запуск Integration Tests (тестирование взаимодействия)

```bash
pytest tests/regression/test_integration_*.py -v
```

**Файлы интеграционных тестов:**
- `test_integration_mtf.py` - Multi-timeframe confluence (REG-A1)
- `test_integration_position.py` - Position management (REG-C1, C3)
- `test_integration_paper.py` - Paper trading mode (REG-E1, E2)
- `test_integration_strategies.py` - All strategies (REG-STR)
- `test_integration_slippage.py` - Slippage model (REG-EXE-003)
- `test_integration_risk.py` - Risk management (REG-RISK)

### 4. Запуск Testnet Tests (реальное API)

**Требует переменных окружения:**

```bash
export BYBIT_API_KEY=your_api_key
export BYBIT_API_SECRET=your_api_secret
```

Или в `.env` файле:

```
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
```

Затем:

```bash
pytest tests/regression/test_testnet_*.py -v -s
```

**Файлы testnet тестов:**
- `test_testnet_api.py` - API authentication & WebSocket (REG-B1-02, B2, B3-03)
- `test_testnet_orders.py` - Order placement/cancellation (REG-C1-02, C2-01, D1)
- `test_testnet_validation.py` - Real data validation (REG-VAL-001)

---

## Полные Regression Suites

### Smoke + Unit (для PR checks)

```bash
pytest smoke_test.py tests/regression/test_unit_*.py -v -q
```

**Time:** ~25 сек  
**Tests:** 35 (6 smoke + 29 unit)  
**Exit code:** 0 if all pass, 1 if any fail

### All (Smoke + Unit + Integration)

```bash
pytest smoke_test.py tests/regression/test_unit_*.py tests/regression/test_integration_*.py -v
```

**Time:** ~1 мин  
**Tests:** 60+

### With Coverage Report

```bash
pytest smoke_test.py tests/regression/test_unit_*.py \
  --cov=bot \
  --cov=strategy \
  --cov=execution \
  --cov=risk \
  --cov-report=html \
  --cov-report=term
```

Результат: `htmlcov/index.html`

---

## CI/CD Workflow (GitHub Actions)

### Файл конфигурации

`.github/workflows/regression.yml`

### Что запускается

**На каждый PR и push:**
- ✅ Smoke tests (block if fail)
- ✅ Unit tests (block if fail)
- ✅ Integration tests (info only)

**Nightly (02:00 UTC):**
- ✅ All tests above
- ✅ Testnet tests (если API доступен)

**На push с [testnet] в комментарии:**
- ✅ All tests including testnet

### Secrets для GitHub Actions

Добавить в repo Settings > Secrets and variables:

```
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
```

---

## Структура Директорий

```
tests/regression/
├── conftest.py                    # Shared fixtures & mocks
├── test_unit_indicators.py        # Unit: A2, A3, A4 (11 tests)
├── test_unit_api.py               # Unit: B1, B3 (5 tests)
├── test_unit_position.py          # Unit: C2, D1, D2 (13 tests)
├── test_integration_mtf.py        # Integration: A1 (4 tests)
├── test_integration_position.py   # Integration: C1, C3 (5 tests)
├── test_integration_paper.py      # Integration: E1, E2 (6 tests)
├── test_integration_strategies.py # Integration: STR (7 tests)
├── test_integration_slippage.py   # Integration: EXE-003 (6 tests)
├── test_integration_risk.py       # Integration: RISK (6 tests)
├── test_testnet_api.py            # Testnet: B1-02, B2, B3-03 (6 tests)
├── test_testnet_orders.py         # Testnet: C1-02, C2-01, D1 (5 tests)
├── test_testnet_validation.py     # Testnet: VAL-001 (6 tests)
└── .reports/                      # JSON test reports (generated)
```

---

## Test Reports

После запуска тестов с `--json-report`:

```bash
pytest tests/regression/ --json-report --json-report-file=tests/regression/.reports/report.json
```

Результаты в `.reports/report.json`

---

## Параллельное выполнение

Для ускорения используйте pytest-xdist:

```bash
pip install pytest-xdist

pytest tests/regression/test_unit_*.py -n auto -v
```

---

## Troubleshooting

### Ошибка: "BYBIT_API_KEY не установлен"

Testnet тесты требуют переменных окружения. Если их нет:

```bash
# Пропустить testnet тесты
pytest tests/regression/test_unit_*.py tests/regression/test_integration_*.py
```

### Ошибка: AttributeError в fixtures

Убедитесь что conftest.py актуальный:

```bash
pytest tests/regression/ --fixtures
```

### Slow tests

Используйте `--durations` для профилирования:

```bash
pytest tests/regression/ --durations=10
```

---

## Examples

### Запустить конкретный тест

```bash
pytest tests/regression/test_unit_indicators.py::TestREGA2_CanonicalColumns::test_feature_pipeline_required_columns -v
```

### Запустить по маркерам

```bash
pytest tests/regression/ -m "not testnet" -v  # Все кроме testnet
pytest tests/regression/ -m "integration" -v  # Только integration
```

### Запустить с логированием

```bash
pytest tests/regression/test_unit_*.py -v --log-cli-level=DEBUG
```

---

## Integration с IDE

### VS Code

Добавить в `.vscode/settings.json`:

```json
{
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests/regression"
  ]
}
```

### PyCharm

Settings > Tools > Python Integrated Tools > Default test runner = pytest

---

## Deploy Checklist

Перед релизом:

- [ ] Smoke tests: 6/6 PASSED
- [ ] Unit tests: 29/29 PASSED
- [ ] Integration tests: 40+/40+ PASSED
- [ ] Testnet tests: все прошли (если есть API)
- [ ] Coverage report: > 80%
- [ ] No deprecation warnings
- [ ] Git workflow: все PR checks зелены

```bash
# Финальная проверка
pytest smoke_test.py tests/regression/test_unit_*.py tests/regression/test_integration_*.py \
  --cov=bot --cov=strategy --cov=execution --cov=risk \
  --cov-fail-under=80 \
  -v --tb=short
```

---

## Next Steps

1. ✅ Smoke tests - ГОТОВЫ
2. ✅ Unit tests - ГОТОВЫ
3. ✅ Integration tests - ГОТОВЫ
4. ✅ Testnet tests - ГОТОВЫ
5. ⏳ CI/CD workflow - READY для GitHub
6. ⏳ HTML reports - можно добавить
7. ⏳ Performance benchmarks - можно добавить
