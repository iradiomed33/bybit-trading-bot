# Быстрое развертывание на VDS (45.8.251.77)

## Автоматическое развертывание (рекомендуется)

### 1. Подключитесь к серверу
```bash
ssh root@45.8.251.77
```

### 2. Скачайте и запустите скрипт развертывания
```bash
# Скачать скрипт напрямую
curl -o deploy.sh https://raw.githubusercontent.com/iradiomed33/bybit-trading-bot/main/deploy.sh

# Или если скрипт еще не в репозитории, создайте его вручную
# (скопируйте содержимое deploy.sh)

# Сделать исполняемым
chmod +x deploy.sh

# Запустить
bash deploy.sh
```

### 3. Следуйте инструкциям скрипта
Скрипт:
- ✅ Установит все необходимое ПО
- ✅ Создаст SSH ключ для GitHub
- ✅ Клонирует репозиторий
- ✅ Установит зависимости
- ✅ Создаст systemd сервис
- ✅ Настроит автозапуск

### 4. Настройте API ключи
```bash
nano /opt/bybit-trading-bot/.env
```
Замените:
- `BYBIT_API_KEY=your_api_key_here`
- `BYBIT_API_SECRET=your_api_secret_here`

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### 5. Запустите бота
```bash
systemctl start bybit-api.service
systemctl status bybit-api.service
```

## Ручное развертывание (пошагово)

Если предпочитаете ручную установку, смотрите [deploy_vds.md](deploy_vds.md)

## Управление сервисом

```bash
# Запуск
systemctl start bybit-api.service

# Остановка
systemctl stop bybit-api.service

# Перезапуск
systemctl restart bybit-api.service

# Статус
systemctl status bybit-api.service

# Логи (в реальном времени)
journalctl -u bybit-api.service -f

# Логи (последние 100 строк)
journalctl -u bybit-api.service -n 100
```

## Обновление кода

```bash
cd /opt/bybit-trading-bot
git pull
systemctl restart bybit-api.service
```

## Доступ к интерфейсу

После запуска веб-интерфейс доступен по адресу:
**http://45.8.251.77:8000**

## Проверка работы API

```bash
# Локально на сервере
curl http://localhost:8000/api/status

# Извне
curl http://45.8.251.77:8000/api/status
```

## Важные пути

- Проект: `/opt/bybit-trading-bot`
- Конфигурация: `/opt/bybit-trading-bot/.env`
- Логи: `journalctl -u bybit-api.service`
- Systemd сервис: `/etc/systemd/system/bybit-api.service`

## Troubleshooting

### Сервис не запускается
```bash
# Проверить синтаксис Python
cd /opt/bybit-trading-bot
source venv/bin/activate
python -m py_compile run_api.py

# Проверить логи
journalctl -u bybit-api.service -n 50 --no-pager
```

### Порт 8000 занят
```bash
# Найти процесс
lsof -i :8000
netstat -tuln | grep 8000

# Убить процесс (если нужно)
kill -9 $(lsof -t -i:8000)
```

### API ключи не загружаются
```bash
# Проверить .env файл
cat /opt/bybit-trading-bot/.env

# Проверить чтение конфигурации
cd /opt/bybit-trading-bot
source venv/bin/activate
python -c "from config import Config; print('API Key loaded:', bool(Config.BYBIT_API_KEY))"
```

### Обновить зависимости
```bash
cd /opt/bybit-trading-bot
source venv/bin/activate
pip install --upgrade -r requirements.txt
systemctl restart bybit-api.service
```

## Безопасность

1. **Настройте firewall:**
```bash
ufw allow 22/tcp
ufw allow 8000/tcp
ufw enable
```

2. **Регулярно обновляйте систему:**
```bash
apt update && apt upgrade -y
```

3. **Создайте отдельного пользователя** (не используйте root в production)

4. **Настройте резервное копирование** файла .env и логов торговли
