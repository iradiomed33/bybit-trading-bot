# Развертывание на VDS (45.8.251.77)

## Шаг 1: Подключение к серверу

```bash
ssh root@45.8.251.77
```

## Шаг 2: Установка необходимого ПО

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Python 3.11, pip, venv и git
apt install -y python3.11 python3.11-venv python3-pip git curl

# Проверка версии Python
python3.11 --version
```

## Шаг 3: Создание SSH ключа для GitHub

```bash
# Создание SSH ключа
ssh-keygen -t ed25519 -C "root@vds-bybit-bot" -f ~/.ssh/id_ed25519 -N ""

# Вывод публичного ключа (скопируйте его)
cat ~/.ssh/id_ed25519.pub
```

**ВАЖНО:** Скопируйте вывод команды выше и добавьте его в GitHub:
1. Перейдите на https://github.com/settings/keys
2. Нажмите "New SSH key"
3. Вставьте скопированный ключ
4. Сохраните

```bash
# Добавление GitHub в known_hosts
ssh-keyscan github.com >> ~/.ssh/known_hosts

# Тест подключения
ssh -T git@github.com
```

## Шаг 4: Клонирование репозитория

```bash
# Переход в рабочую директорию
cd /opt

# Клонирование репозитория
git clone git@github.com:iradiomed33/bybit-trading-bot.git

# Переход в директорию проекта
cd bybit-trading-bot

# Переключение на нужную ветку (если требуется)
git checkout copilot/fix-live-component-initialization
```

## Шаг 5: Создание виртуального окружения и установка зависимостей

```bash
# Создание виртуального окружения
python3.11 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt
```

## Шаг 6: Настройка конфигурации

```bash
# Создание .env файла
cat > .env << 'EOF'
# Bybit API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=false

# Trading Configuration
SYMBOL=BTCUSDT
LEVERAGE=10

# Dashboard Configuration
DASHBOARD_PORT=8000
DASHBOARD_HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO
EOF

# Редактирование .env файла с вашими реальными ключами
nano .env
```

**ВАЖНО:** Замените `your_api_key_here` и `your_api_secret_here` на ваши реальные API ключи от Bybit!

## Шаг 7: Создание systemd сервиса для API Dashboard

```bash
cat > /etc/systemd/system/bybit-api.service << 'EOF'
[Unit]
Description=Bybit Trading Bot API Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bybit-trading-bot
Environment="PATH=/opt/bybit-trading-bot/venv/bin"
ExecStart=/opt/bybit-trading-bot/venv/bin/python /opt/bybit-trading-bot/run_api.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

## Шаг 8: Запуск сервисов

```bash
# Перезагрузка systemd
systemctl daemon-reload

# Включение автозапуска сервиса
systemctl enable bybit-api.service

# Запуск сервиса
systemctl start bybit-api.service

# Проверка статуса
systemctl status bybit-api.service

# Просмотр логов
journalctl -u bybit-api.service -f
```

## Шаг 9: Настройка firewall (опционально)

```bash
# Если используется ufw
ufw allow 8000/tcp
ufw allow 22/tcp
ufw enable
```

## Шаг 10: Проверка работы

```bash
# Проверка, что API отвечает
curl http://localhost:8000/api/status

# Проверка доступности извне
curl http://45.8.251.77:8000/api/status
```

## Полезные команды для управления

```bash
# Остановка сервиса
systemctl stop bybit-api.service

# Перезапуск сервиса
systemctl restart bybit-api.service

# Просмотр логов
journalctl -u bybit-api.service -f --no-pager

# Обновление кода из репозитория
cd /opt/bybit-trading-bot
git pull
systemctl restart bybit-api.service
```

## Доступ к веб-интерфейсу

После успешного запуска, веб-интерфейс будет доступен по адресу:
- http://45.8.251.77:8000

## Troubleshooting

### Проблема с правами доступа
```bash
chmod +x /opt/bybit-trading-bot/run_api.py
chown -R root:root /opt/bybit-trading-bot
```

### Проблема с портом 8000
```bash
# Проверка, что порт свободен
netstat -tuln | grep 8000

# Или найти процесс, использующий порт
lsof -i :8000
```

### Проверка переменных окружения
```bash
# Проверка, что .env файл читается
cd /opt/bybit-trading-bot
source venv/bin/activate
python -c "from config import Config; print(Config.BYBIT_API_KEY[:10])"
```
