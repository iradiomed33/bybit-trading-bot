# Bybit Trading Bot

Автоматический торговый бот для деривативов на Bybit API V5.

## 🚀 Быстрый старт

```bash
# 1. Проверка системы
python cli.py health

# 2. Просмотр конфигурации  
python cli.py config show

# 3. Запуск (paper mode - безопасно)
python cli.py paper

# 4. Или запуск live (ОСТОРОЖНО! Реальные деньги)
python cli.py live

# 5. Валидировать стратегию перед live
python -m examples.validate_sample_strategy
```

## 🧪 E2E Testing

**TASK-QA-UI-SETTINGS-001** ✅ Автотесты UI настроек

Гарантирует что настройки UI **реально** влияют на бота:

```bash
# Quick start (Windows)
.\run_e2e_tests.bat

# Quick start (Linux/Mac)
./run_e2e_tests.sh

# Или вручную
cd tests/e2e
npm install
npx playwright install
npm test
```

**Что тестируется:**
- ✅ Basic settings → runtime config (leverage, SL/TP, risk)
- ✅ Advanced settings → order intent (ATR mult, MTF, no-trade zones)
- ✅ Validation logic (недопустимые значения блокируются)
- ✅ Dry-run mode (без реальных ордеров)

Подробнее: [tests/e2e/README.md](tests/e2e/README.md)

## 🎓 EPIC V: Validation — Stop Trusting By Eye

**VAL-001 | Unified Validation Pipeline** ✅ Production Ready

Ensures identical logic across backtest/forward/live trading:

```python
from execution.backtest_runner import BacktestRunner

runner = BacktestRunner()
report = runner.run_unified_validation(
    df=data,
    strategy_func=my_strategy,
    strategy_name="MyStrategy",
)

print(f"Train PF: {report.train_metrics.profit_factor:.2f}")
print(f"Test PF:  {report.test_metrics.profit_factor:.2f}")
print(f"Valid:    {report.is_valid}")
```

**Features**:
- ✅ Canonical pipeline (same code for backtest/forward/live)
- ✅ 27 comprehensive metrics (PF, DD, expectancy, exposure)
- ✅ Transparent fee reporting (commission + slippage)
- ✅ Out-of-sample validation (train/test split, no leakage)
- ✅ Degradation detection (overfitting warning)
- ✅ 19 unit tests, 434 total tests passing

**Documentation**: [docs/VAL-001-Unified-Validation.md](docs/VAL-001-Unified-Validation.md)

## 🔧 Управление конфигурацией

Все настройки в [config/bot_settings.json](config/bot_settings.json).

```bash
# Изменить символ
python cli.py config set trading.symbol ETHUSDT

# Изменить риск
python cli.py config set risk_management.position_risk_percent 2.0

# Показать раздел
python cli.py config section risk_management

# Валидировать
python cli.py config validate
```

**Полная документация**: [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

## 🎯 Режимы работы
- **backtest** - Исторический прогон на исторических данных (с VAL-001 validation)
- **paper** - Симуляция торговли без реальных денег
- **live** - Реальная торговля (используй TESTNET первым!)

## 📋 Установка (Windows)

1. Установите Python 3.10+
2. Клонируйте репозиторий
3. Установите зависимости:
```bash
pip install -r requirements.txt
