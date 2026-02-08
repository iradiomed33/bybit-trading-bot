# Исправление Бага Сброса Kill Switch

## Описание Проблемы

Пользователь не мог перезапустить бота после активации kill switch, даже после нажатия кнопки сброса в UI. Бот выдавал ошибку:

```
2026-02-07 19:50:02 | WARNING | risk.kill_switch | Kill switch was previously activated (found in DB)
2026-02-07 19:50:02 | ERROR | bot.trading_bot | Kill switch is active! Cannot start. Reset with confirmation first.
```

## Корневая Причина

В коде использовались **два разных класса** kill switch, которые работали независимо:

### 1. KillSwitch (risk/kill_switch.py)
- Сохраняет активацию в таблице `errors`
- Метод `check_status()` проверяет наличие записей в таблице errors
- Метод `reset()` удаляет записи из таблицы errors

### 2. KillSwitchManager (execution/kill_switch.py)
- Сохраняет флаг `trading_disabled` в таблице `config`
- Метод `can_trade()` проверяет флаг в БД
- Метод `reset()` очищает флаг `trading_disabled`

### Проблема
- API эндпоинт `/api/bot/reset_killswitch` сбрасывал **только** старый KillSwitch
- Бот при старте проверял **только** старый KillSwitch через `check_status()`
- **НО** KillSwitchManager также устанавливал флаг `trading_disabled` при активации
- В результате флаг `trading_disabled` оставался True, блокируя запуск

## Решение

### 1. Добавлена таблица config в Database (storage/database.py)
```sql
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

### 2. Реализованы методы save_config() и get_config()
```python
def save_config(self, key: str, value: Any) -> None:
    """Сохранить конфигурационный параметр"""
    # Сохраняет значение как JSON

def get_config(self, key: str, default: Any = None) -> Any:
    """Получить конфигурационный параметр"""
    # Возвращает значение или default
```

### 3. Обновлен API endpoint для сброса обоих kill switches (api/app.py)
```python
@app.post("/api/bot/reset_killswitch")
async def reset_killswitch():
    # 1. Сбросить старый KillSwitch (таблица errors)
    kill_switch = KillSwitch(db)
    success_old = kill_switch.reset("RESET")
    
    # 2. Сбросить KillSwitchManager (флаг trading_disabled)
    # Либо через manager.reset(), либо напрямую db.save_config()
    ...
```

### 4. Добавлена проверка обоих флагов при старте бота (bot/trading_bot.py)
```python
def run(self):
    # Проверка старого KillSwitch
    if self.kill_switch.check_status():
        logger.error("Kill switch is active! Cannot start.")
        return
    
    # Проверка KillSwitchManager (флаг trading_disabled)
    if self.mode == "live" and self.kill_switch_manager:
        if not self.kill_switch_manager.can_trade():
            logger.error("Trading is disabled! Cannot start.")
            return
```

## Тестирование

Создан комплексный тест `test_killswitch_reset_fix.py` который проверяет:
- ✅ Сброс старого KillSwitch (таблица errors)
- ✅ Сброс нового KillSwitchManager (флаг trading_disabled)
- ✅ Комбинированный сброс через API
- ✅ После сброса бот может запуститься

**Все тесты проходят успешно!**

## Результат

Теперь кнопка сброса kill switch в UI корректно:
1. Сбрасывает записи в таблице `errors` (старый механизм)
2. Очищает флаг `trading_disabled` в таблице `config` (новый механизм)
3. Позволяет боту успешно запуститься после сброса

## Дополнительные Улучшения

1. **Улучшена обработка ошибок**: При сбое декодирования JSON в `get_config()` возвращается default вместо поврежденных данных
2. **Fallback механизм**: Если KillSwitchManager не может быть создан, флаг `trading_disabled` сбрасывается напрямую в БД
3. **CodeQL проверка**: Не обнаружено уязвимостей безопасности

## Затронутые Файлы

- `api/app.py` - обновлен endpoint `/api/bot/reset_killswitch`
- `bot/trading_bot.py` - добавлена проверка флага `trading_disabled` при старте
- `storage/database.py` - добавлена таблица config и методы save_config/get_config
- `test_killswitch_reset_fix.py` - новый тест для проверки исправления
