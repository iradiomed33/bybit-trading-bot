# 🔄 Быстрое переключение между профилями настроек

## 3 готовых профиля

```
config/
├── bot_settings.json                      (текущий, используется ботом)
├── bot_settings_AGGRESSIVE_TESTNET.json   (для тестирования)
└── bot_settings_PRODUCTION.json           (для продакшена)
```

---

## 🚀 Быстрое переключение

### Опция 1: Через Dashboard (безопасно) ✅

1. Откройте Settings ⚙️
2. Измените параметры вручную
3. Нажмите Save

**Плюсы:**
- ✅ Видны изменения в реальном времени
- ✅ Можно менять по одному параметру
- ✅ Безопасно (бот работает)

---

### Опция 2: Копирование файла (быстро) ⚡

#### Windows PowerShell:

**Переключиться на АГРЕССИВНЫЙ профиль:**
```powershell
Copy-Item config\bot_settings_AGGRESSIVE_TESTNET.json config\bot_settings.json -Force
Write-Host "✓ Aggressive testnet settings loaded"
```

**Переключиться на PRODUCTION:**
```powershell
Copy-Item config\bot_settings_PRODUCTION.json config\bot_settings.json -Force
Write-Host "✓ Production settings loaded"
```

**Вернуться к текущему:**
```powershell
# Просто скопировать свой backup
Copy-Item config\bot_settings.json.backup config\bot_settings.json -Force
```

---

#### Linux/Mac:

**Переключиться на АГРЕССИВНЫЙ:**
```bash
cp config/bot_settings_AGGRESSIVE_TESTNET.json config/bot_settings.json
echo "✓ Aggressive testnet settings loaded"
```

**Переключиться на PRODUCTION:**
```bash
cp config/bot_settings_PRODUCTION.json config/bot_settings.json
echo "✓ Production settings loaded"
```

---

### Опция 3: Python скрипт (проверка)

**switch_settings.py:**
```python
#!/usr/bin/env python3
import shutil
import sys
import json
from pathlib import Path

def switch_profile(profile: str):
    """Переключить на профиль настроек"""
    config_dir = Path("config")
    
    profiles = {
        "aggressive": "bot_settings_AGGRESSIVE_TESTNET.json",
        "production": "bot_settings_PRODUCTION.json",
        "default": "bot_settings.json"
    }
    
    if profile not in profiles:
        print(f"❌ Неизвестный профиль: {profile}")
        print(f"   Доступные: {', '.join(profiles.keys())}")
        return False
    
    source = config_dir / profiles[profile]
    target = config_dir / "bot_settings.json"
    
    if not source.exists():
        print(f"❌ Файл не найден: {source}")
        return False
    
    # Backup текущего
    backup = target.with_suffix('.json.backup')
    if target.exists():
        shutil.copy2(target, backup)
        print(f"✓ Backup сохранён: {backup}")
    
    # Копировать новый
    shutil.copy2(source, target)
    
    # Показать что изменилось
    with open(target) as f:
        config = json.load(f)
    
    print(f"\n✓ Профиль '{profile}' загружен")
    print(f"  - Risk: {config['risk_management']['position_risk_percent']}%")
    print(f"  - Max Position: {config['risk_management']['max_position_size']}")
    print(f"  - SL: {config['risk_management']['stop_loss_percent']}%")
    print(f"  - TP: {config['risk_management']['take_profit_percent']}%")
    print(f"  - Volatility Filter: {config['meta_layer']['volatility_filter_enabled']}")
    
    return True

if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "aggressive"
    switch_profile(profile)
```

**Использование:**
```bash
python switch_settings.py aggressive   # Загрузить агрессивный профиль
python switch_settings.py production   # Загрузить продакшен
```

---

## 📊 Сравнение профилей

| Параметр | Aggressive | Production |
|----------|-----------|-----------|
| **Risk** | 5% | 0.5% |
| **Max Position** | 0.5 | 0.05 |
| **Stop Loss** | 5% | 2% |
| **Take Profit** | 10% | 5% |
| **TrendPullback confidence** | 0.35 | 0.60 |
| **Breakout confidence** | 0.35 | 0.65 |
| **MeanReversion confidence** | 0.30 | 0.55 |
| **Volatility Filter** | OFF | ON |
| **Breakeven** | OFF | ON |
| **Partial Exit** | OFF | ON |
| **Testnet** | true | false |
| **Leverage** | 10x | 5x |

---

## ⚠️ ВАЖНЫЕ моменты

### Когда менять настройки:

✅ **МОЖНО менять во время работы бота:**
- Через Dashboard (Settings)
- Файл `bot_settings.json` автоматически перечитывается

❌ **НЕЛЬЗЯ просто стирать файл:**
- Бот перестанет работать
- Используйте backup или версию по умолчанию

---

### Перед переходом на PRODUCTION:

1. ✅ Протестировать на TESTNET минимум 3-5 дней
2. ✅ Убедиться что бот стабилен 24+ часа
3. ✅ Вернуть консервативные настройки (PRODUCTION профиль)
4. ✅ Начать с маленькой суммой денег
5. ✅ Мониторить первые 24 часа

```bash
# Перед продакшеном:
Copy-Item config\bot_settings_PRODUCTION.json config\bot_settings.json -Force
```

---

## 🔍 Как проверить какой профиль загружен

```bash
# Linux/Mac:
cat config/bot_settings.json | grep -A 5 "risk_management"

# Windows:
Get-Content config\bot_settings.json | Select-String -A 5 "risk_management"
```

Или в Dashboard → Settings → посмотреть текущие значения.

---

## 📝 Создание своего профиля

Если хотите свой профиль:

```bash
# 1. Копировать существующий
cp config/bot_settings.json config/bot_settings_CUSTOM.json

# 2. Отредактировать
nano config/bot_settings_CUSTOM.json

# 3. Использовать
cp config/bot_settings_CUSTOM.json config/bot_settings.json
```

---

## 🚨 Recover если что-то сломалось

```bash
# Вернуться к предыдущему состоянию:
Copy-Item config\bot_settings.json.backup config\bot_settings.json -Force

# Или загрузить дефолтный:
Copy-Item config\bot_settings_AGGRESSIVE_TESTNET.json config\bot_settings.json -Force
```

---

## 📋 Checklist перед запуском

```
Aggressive (TESTNET):
[ ] risk = 5%
[ ] max_position = 0.5
[ ] volatility_filter = false
[ ] testnet = true
[ ] confidence_threshold (низкие пороги)

Production (MAINNET):
[ ] risk = 0.5%
[ ] max_position = 0.05
[ ] volatility_filter = true
[ ] testnet = false
[ ] confidence_threshold (высокие пороги)
[ ] leverage = 5x (не 10x!)
```

---

**Версия:** 1.0  
**Дата:** 2026-02-04  
**Статус:** Ready
