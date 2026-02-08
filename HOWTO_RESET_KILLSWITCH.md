# Как сбросить Kill Switch

## Проблема
После активации kill switch бот не может запуститься и выдает ошибку:
```
WARNING | risk.kill_switch | Kill switch was previously activated (found in DB)
ERROR | bot.trading_bot | Kill switch is active! Cannot start. Reset with confirmation first.
```

## Решение

### Вариант 1: Через командную строку (РЕКОМЕНДУЕТСЯ)

Запустите скрипт сброса:

```bash
python reset_killswitch.py
```

Скрипт:
1. Проверит текущий статус kill switch
2. Запросит подтверждение (введите `RESET`)
3. Сбросит оба механизма kill switch:
   - Удалит записи из таблицы `errors`
   - Очистит флаг `trading_disabled`
4. Проверит результат

После успешного сброса вы увидите:
```
✅ СБРОС УСПЕШНО ЗАВЕРШЕН!
Бот теперь можно запустить.
```

### Вариант 2: Через UI (Dashboard)

1. Откройте веб-интерфейс бота
2. Найдите кнопку "Reset Kill Switch" или "Сбросить Kill Switch"
3. Нажмите кнопку
4. Подтвердите сброс

### Вариант 3: Напрямую через базу данных (НЕ РЕКОМЕНДУЕТСЯ)

Только если оба варианта выше не работают:

```bash
sqlite3 storage/bot_state.db "DELETE FROM errors WHERE error_type = 'kill_switch_activated';"
sqlite3 storage/bot_state.db "DELETE FROM config WHERE key = 'trading_disabled';"
```

## Проверка

После сброса запустите бот:
```bash
python cli.py --mode live
```

Бот должен успешно запуститься без ошибок о kill switch.

## Почему это происходит?

Kill switch - это механизм аварийной остановки, который активируется при:
- Критических ошибках
- Превышении риск-лимитов
- Ручной активации

После активации kill switch блокирует запуск бота до тех пор, пока не будет **явно сброшен** с подтверждением. Это сделано специально, чтобы предотвратить автоматический перезапуск бота после серьезных проблем.

## Дополнительная информация

См. документацию: `KILLSWITCH_RESET_FIX.md`
