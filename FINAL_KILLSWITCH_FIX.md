# Финальное Исправление: Kill Switch Reset

## Проблема, о которой сообщил пользователь

После первого исправления пользователь все равно видел ошибку:
```
2026-02-08 04:26:50 | WARNING | risk.kill_switch | Kill switch was previously activated (found in DB)
2026-02-08 04:26:50 | ERROR | bot.trading_bot | Kill switch is active! Cannot start. Reset with confirmation first.
```

## Корневая Причина

**Двойная проблема:**

1. **Пользователь не знал как сбросить kill switch** - API endpoint существовал, но не было удобного CLI инструмента
2. **Существующая CLI команда была неполной** - команда `cli.py reset-kill-switch` удаляла только записи из errors table (и то только за последние 24 часа), но НЕ сбрасывала флаг `trading_disabled`

## Полное Решение

### 1. Создан отдельный интерактивный скрипт `reset_killswitch.py`

**Преимущества:**
- Независимый скрипт - легко найти и запустить
- Интерактивный - показывает текущий статус, запрашивает подтверждение
- Подробный вывод - пользователь видит что именно сбрасывается
- Проверка результата - подтверждает успешность сброса

**Использование:**
```bash
python reset_killswitch.py
```

### 2. Исправлена CLI команда `cli.py reset-kill-switch`

**До исправления:**
```python
# Удаляло только записи из errors за 24 часа
cursor.execute("""
    DELETE FROM errors
    WHERE error_type = 'kill_switch_activated'
    AND timestamp > ?
""", (last_24h,))
```

**После исправления:**
```python
# 1. Использует правильный метод KillSwitch.reset()
kill_switch = KillSwitch(db)
success_old = kill_switch.reset("RESET")  # Удаляет ВСЕ записи

# 2. Сбрасывает флаг trading_disabled
db.save_config("trading_disabled", False)
```

### 3. Добавлены инструкции для пользователя

- **`СРОЧНО_СБРОС_KILLSWITCH.md`** - краткая инструкция на русском с быстрым решением
- **`HOWTO_RESET_KILLSWITCH.md`** - подробная инструкция со всеми способами

## Три Способа Сброса (все работают одинаково)

### Способ 1: CLI команда (РЕКОМЕНДУЕТСЯ)
```bash
python cli.py reset-kill-switch
# Введите RESET для подтверждения
```

### Способ 2: Отдельный скрипт
```bash
python reset_killswitch.py
# Введите RESET для подтверждения
```

### Способ 3: Через UI
Откройте веб-интерфейс и нажмите кнопку "Reset Kill Switch"

## Что сбрасывается (во всех трех способах)

1. **KillSwitch (risk/kill_switch.py)**
   - Удаляет ВСЕ записи `error_type = 'kill_switch_activated'` из таблицы `errors`
   - Сбрасывает внутренний флаг `is_activated = False`

2. **KillSwitchManager (execution/kill_switch.py)**
   - Очищает флаг `trading_disabled` в таблице `config`
   - Устанавливает `is_halted = False`

## Проверка Работы

После сброса bot должен запуститься без ошибок:
```bash
python cli.py live
# ИЛИ
python run_bot.py
```

Успешный запуск:
```
INFO | bot.trading_bot | Starting bot in LIVE mode...
INFO | bot.trading_bot | Running initial reconciliation...
INFO | bot.trading_bot | Bot started successfully
```

## Тестирование

Все тесты проходят:
- ✅ `test_reset_script.py` - тестирует логику сброса
- ✅ `test_cli_reset.py` - тестирует CLI команду
- ✅ `test_killswitch_reset_fix.py` - тестирует оба механизма
- ✅ CodeQL проверка - 0 уязвимостей

## Изменения в Коде

**Файлы:**
1. `cli.py` - исправлена функция `reset_kill_switch()`
2. `reset_killswitch.py` - новый интерактивный скрипт
3. `СРОЧНО_СБРОС_KILLSWITCH.md` - краткая инструкция
4. `HOWTO_RESET_KILLSWITCH.md` - подробная инструкция

**Никаких изменений в:**
- `api/app.py` - endpoint уже был исправлен ранее
- `bot/trading_bot.py` - проверка обоих флагов уже была добавлена
- `storage/database.py` - методы save_config/get_config уже были добавлены

## Итог

Теперь у пользователя есть **три простых способа** сбросить kill switch, и все они работают корректно, сбрасывая оба механизма. Проблема полностью решена.
