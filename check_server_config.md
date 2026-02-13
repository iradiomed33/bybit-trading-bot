# Проверка конфигурации на сервере

На сервере выполните:

```bash
# 1. Проверить какой kline_interval в bot_settings.json на сервере
cd /opt/bybit-trading-bot
cat config/bot_settings.json | grep kline_interval

# 2. Проверить версию файла
cat config/bot_settings.json | grep _version

# 3. Проверить timestamp последнего обновления
cat config/bot_settings.json | grep _updated_at
```

## Возможные причины расхождения:

### 1. **bot_settings.json на сервере не обновлен**
- Локальный файл: `"kline_interval": "60"`
- Серверный файл: возможно `"kline_interval": "1"`
- **Решение:** Скопировать обновленный bot_settings.json на сервер

### 2. **UI показывает кэшированные данные**
- Браузер кэширует старый GET /api/config ответ
- **Решение:** 
  - Ctrl+Shift+R (hard refresh в браузере)
  - Очистить кэш браузера
  - Проверить в DevTools → Network → Disable cache

### 3. **Изменения через UI не сохраняются**
- POST /api/config работает локально, но на сервере может быть проблема с правами на запись
- **Проверка:**
  ```bash
  # Проверить права на файл
  ls -la /opt/bybit-trading-bot/config/bot_settings.json
  
  # Должен быть owner:group у пользователя который запускает API
  # Права должны быть rw-r--r-- (644) или rw-rw-r-- (664)
  ```

## Как синхронизировать:

### Вариант A: Обновить настройку через UI
1. Открыть UI в браузере
2. Settings → Market Data → Timeframe
3. Выбрать "1m" (1 минута)
4. Нажать Save
5. Проверить что _version увеличился в bot_settings.json на сервере

### Вариант B: Скопировать актуальный bot_settings.json
```bash
# Создать резервную копию на сервере
cp /opt/bybit-trading-bot/config/bot_settings.json /opt/bybit-trading-bot/config/bot_settings.json.backup

# Затем через WinSCP/SFTP скопировать обновленный файл с вашего компьютера
# ИЛИ отредактировать напрямую на сервере:
nano /opt/bybit-trading-bot/config/bot_settings.json
# Найти "kline_interval": "60" и изменить на "kline_interval": "1"
```

### Вариант C: Установить через API (curl)
```bash
curl -X POST http://localhost:8000/api/config/market_data.kline_interval \
  -H "Content-Type: application/json" \
  -d '{"value": "1"}'
```

## Перезапуск после изменения

После обновления конфигурации:
1. Остановить бота в UI (Stop Bot)
2. Подождать 3-5 секунд
3. Запустить бота снова (Start Bot)
4. Проверить логи - должно появиться: `interval=1m, last_bar_ts=...`
