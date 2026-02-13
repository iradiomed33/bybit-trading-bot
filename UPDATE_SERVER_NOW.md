# СРОЧНО: Обновить код на сервере

## Проблема
На сервере запущен СТАРЫЙ код с 404 ошибками.
Все исправления (4 коммита) НЕ ПРИМЕНЕНЫ.

## Срочные действия на сервере:

```bash
# 1. Остановить бота
sudo systemctl stop bybit-api.service

# 2. Обновить код
cd /opt/bybit-trading-bot
git pull

# Вы должны увидеть:
# Updating fb5effd..a18936a
# Fast-forward
#  api/app.py                    | 9 ++++++++-
#  bot/trading_bot.py            | 2 +-
#  execution/kill_switch.py      | 2 +-
#  3 files changed, 10 insertions(+), 3 deletions(-)

# 3. Перезапустить сервис
sudo systemctl restart bybit-api.service

# 4. Проверить логи
tail -f logs/bot_*.log

# Должны исчезнуть ошибки:
# ✅ Нет 404 для /v5/position/list
# ✅ Нет NameError
# ✅ Config reload работает
```

## Что будет исправлено:

1. ✅ Kill Switch будет правильно закрывать позиции (GET вместо POST)
2. ✅ Не будет NameError в trading_bot.py
3. ✅ UI настройки будут влиять на бота (reload config)
4. ✅ Фильтр сигналов в UI будет работать

## ВАЖНО:
Пока вы не обновите код - все 4 критических бага АКТИВНЫ!
