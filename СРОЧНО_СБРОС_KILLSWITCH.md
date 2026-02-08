# ⚠️ РЕШЕНИЕ ПРОБЛЕМЫ: Kill Switch Активирован

## Если вы видите эту ошибку:

```
WARNING | risk.kill_switch | Kill switch was previously activated (found in DB)
ERROR | bot.trading_bot | Kill switch is active! Cannot start. Reset with confirmation first.
```

## БЫСТРОЕ РЕШЕНИЕ:

### Способ 1 (РЕКОМЕНДУЕТСЯ):
```bash
python cli.py reset-kill-switch
```
Введите `RESET` когда попросят подтверждение.

### Способ 2:
```bash
python reset_killswitch.py
```
Введите `RESET` когда попросят подтверждение.

### Способ 3 (через UI):
Откройте веб-интерфейс и найдите кнопку "Reset Kill Switch"

---

## После сброса:
Запустите бот как обычно:
```bash
python cli.py live
```

## Подробная информация:
См. файл `HOWTO_RESET_KILLSWITCH.md`

---

**ВНИМАНИЕ**: Kill switch активируется автоматически при критических ошибках или превышении риск-лимитов. Перед сбросом убедитесь, что причина активации устранена!
