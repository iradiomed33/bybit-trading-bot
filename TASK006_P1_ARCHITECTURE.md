## TASK-006 Phase 1: Архитектура единого источника истины

### Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI/API/Tests                           │
│                                                               │
│  cli.py        smoke_test.py       test_*.py               │
│  (10 places)   (5 places)          (implicit)              │
└───────────────────┬───────────────────────────────────────┘
                    │
                    │ testnet = ConfigManager().is_testnet()
                    │ or
                    │ testnet = config.is_testnet()
                    │
                    ▼
        ┌─────────────────────────────────┐
        │   ConfigManager.is_testnet()    │
        │   (ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ)      │
        └──────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌──────────┐
   │Priority│ │Priority│ │Priority 3│
   │   1    │ │   2    │ │          │
   └────────┘ └────────┘ └──────────┘
        │          │          │
        │          │          │
   ENVIRONMENT  JSON config   Default
   (env var)  (bot_settings.  (testnet)
              json)
```

### Приоритет определения

```
┌─────────────────────────────────────────────────┐
│  1️⃣  ENVIRONMENT env variable                  │
│      (Highest Priority - User explicit intent) │
│      Example: ENVIRONMENT=mainnet              │
└─────────────────────────────────────────────────┘
                    ▼ (if not set)
┌─────────────────────────────────────────────────┐
│  2️⃣  trading.testnet JSON config               │
│      (Fallback - Configuration file)            │
│      Example: "testnet": true                   │
└─────────────────────────────────────────────────┘
                    ▼ (if not set)
┌─────────────────────────────────────────────────┐
│  3️⃣  Default: True (testnet)                   │
│      (Lowest Priority - Safe default)           │
│      Won't trade real money by accident         │
└─────────────────────────────────────────────────┘
```

### Таблица истинности

| ENVIRONMENT | trading.testnet | Result  | Source |
|-------------|-----------------|---------|--------|
| "testnet"   | true            | testnet | ENV ✓  |
| "testnet"   | false           | testnet | ENV ✓  |
| "testnet"   | (not set)       | testnet | ENV ✓  |
| "mainnet"   | true            | mainnet | ENV ✓  |
| "mainnet"   | false           | mainnet | ENV ✓  |
| "mainnet"   | (not set)       | mainnet | ENV ✓  |
| (not set)   | true            | testnet | JSON   |
| (not set)   | false           | mainnet | JSON   |
| (not set)   | (not set)       | testnet | DEF    |

### Места в коде

#### CLI (10 мест обновлено)

```
cli.py:
  Line  195: market_data_test()      → testnet = ConfigManager().is_testnet()
  Line  309: stream_test()           → testnet = ConfigManager().is_testnet()
  Line  441: state_recovery_test()   → testnet = ConfigManager().is_testnet()
  Line  503: features_test()         → testnet = ConfigManager().is_testnet()
  Line  793: execution_test()        → testnet = ConfigManager().is_testnet()
  Line  956: strategy_test()         → testnet = ConfigManager().is_testnet()
  Line 1105: backtest_command()      → testnet = config.is_testnet()
  Line 1280: paper_command()         → testnet = config.is_testnet()
  Line 1330: live_command()          → testnet = config.is_testnet()
  Line 1438: kill_command()          → testnet = ConfigManager().is_testnet()
```

#### Smoke Tests (5 мест обновлено)

```
smoke_test.py:
  Line  106: test_smk_02_market_data()    → testnet=ConfigManager().is_testnet()
  Line  153: test_smk_03_features()       → testnet=ConfigManager().is_testnet()
  Line  225: test_smk_04_bot_init()       → testnet=ConfigManager().is_testnet()
  Line  261: test_smk_05_account()        → testnet=ConfigManager().is_testnet()
  Line  298: test_smk_06_kill_switch()    → testnet=ConfigManager().is_testnet()
```

### Результаты тестирования

```
╔═══════════════════════════════════════════════╗
║  TASK-006 Phase 1 Test Results               ║
╠═══════════════════════════════════════════════╣
║  Environment Detection Tests:        22/22 ✅ ║
║  TASK-005 Phase 2 Regression:       34/34 ✅ ║
║  Config Tests:                        6/6 ✅ ║
║  Smoke Tests (SMK-01 to SMK-06):      6/6 ✅ ║
╠═══════════════════════════════════════════════╣
║  TOTAL:                              68/68 ✅ ║
║  Success Rate:                      100% 🎉  ║
╚═══════════════════════════════════════════════╝
```

### Команды для тестирования

```bash
# Запустить TASK-006 Phase 1 тесты
python -m pytest tests/test_task006_phase1_environment.py -v

# Убедиться что TASK-005 все еще работает
python -m pytest tests/test_task005_phase2_risk_params.py -v

# Запустить smoke tests
python smoke_test.py

# Запустить CLI с разными окружениями
ENVIRONMENT=testnet python cli.py paper     # Использует ENVIRONMENT
ENVIRONMENT=mainnet python cli.py live      # Использует ENVIRONMENT
python cli.py backtest                      # Использует JSON или default
```

### Логирование источника

Каждый вызов `is_testnet()` логирует свой источник:

```
[DEBUG] [Environment] Using testnet (from ENVIRONMENT env var)
[DEBUG] [Environment] Using mainnet (from config/bot_settings.json)
[DEBUG] [Environment] Using testnet (default)
```

### Импорты в коде

```python
# Для функций с config контекстом
config = ConfigManager()
result = config.is_testnet()

# Для функций без config контекста
from config.settings import ConfigManager
result = ConfigManager().is_testnet()

# Для получения строки "testnet"/"mainnet"
env_string = ConfigManager().get_environment()
```

### Гарантии безопасности

✅ Нет возможности десинхронизации между CLI и API  
✅ ENVIRONMENT переменная гарантирует строгое управление  
✅ JSON конфиг служит резервным источником  
✅ Дефолт на testnet предотвращает случайные операции с реальными деньгами  
✅ Логирование показывает какой источник использован  

### Обратная совместимость

✅ Config.ENVIRONMENT все еще работает (для старого кода)  
✅ trading.testnet все еще доступен через config.get()  
✅ Все существующие тесты (TASK-005, smoke tests) работают  
✅ Нет breaking changes в публичных API  

---

**Статус**: 🟢 Production Ready  
**Дата**: 2026-02-08  
**Версия**: Phase 1 Complete
