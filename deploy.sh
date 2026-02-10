#!/bin/bash

# Скрипт автоматического развертывания Bybit Trading Bot на VDS
# Использование: bash deploy.sh

set -e  # Остановка при ошибке

echo "================================================"
echo "  Развертывание Bybit Trading Bot на VDS"
echo "================================================"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Шаг 1: Проверка ОС
log_info "Проверка операционной системы..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log_info "ОС: $NAME $VERSION"
else
    log_error "Не удалось определить ОС"
    exit 1
fi

# Шаг 2: Обновление системы
log_info "Обновление системы..."
apt update -y
apt upgrade -y

# Шаг 3: Установка необходимого ПО
log_info "Установка необходимого ПО (Python 3.11, git, curl)..."
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa || true
apt update -y
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip git curl build-essential

# Проверка установки Python
if command -v python3.11 &> /dev/null; then
    log_info "Python установлен: $(python3.11 --version)"
else
    log_error "Не удалось установить Python 3.11"
    exit 1
fi

# Шаг 4: Создание SSH ключа для GitHub
log_info "Проверка SSH ключа для GitHub..."
if [ ! -f ~/.ssh/id_ed25519 ]; then
    log_info "Создание нового SSH ключа..."
    ssh-keygen -t ed25519 -C "root@vds-bybit-bot" -f ~/.ssh/id_ed25519 -N ""
    log_info "SSH ключ создан!"
    echo ""
    echo "================================================"
    log_warn "ВАЖНО! Добавьте этот SSH ключ в GitHub:"
    echo "================================================"
    cat ~/.ssh/id_ed25519.pub
    echo "================================================"
    echo ""
    echo "1. Перейдите на https://github.com/settings/keys"
    echo "2. Нажмите 'New SSH key'"
    echo "3. Вставьте ключ выше"
    echo "4. Нажмите 'Add SSH key'"
    echo ""
    read -p "Нажмите Enter после добавления ключа в GitHub..."
else
    log_info "SSH ключ уже существует"
fi

# Добавление GitHub в known_hosts
log_info "Добавление GitHub в known_hosts..."
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null

# Тест подключения к GitHub
log_info "Тестирование подключения к GitHub..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    log_info "Подключение к GitHub успешно!"
else
    log_warn "Проверьте подключение к GitHub: ssh -T git@github.com"
fi

# Шаг 5: Клонирование репозитория
INSTALL_DIR="/opt/bybit-trading-bot"
log_info "Клонирование репозитория в $INSTALL_DIR..."

if [ -d "$INSTALL_DIR" ]; then
    log_warn "Директория $INSTALL_DIR уже существует"
    read -p "Удалить старую версию и клонировать заново? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Удаление старой директории..."
        rm -rf "$INSTALL_DIR"
        git clone git@github.com:iradiomed33/bybit-trading-bot.git "$INSTALL_DIR"
    else
        log_info "Обновление существующего репозитория..."
        cd "$INSTALL_DIR"
        git fetch --all
        git pull
    fi
else
    git clone git@github.com:iradiomed33/bybit-trading-bot.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Выбор ветки
log_info "Текущая ветка: $(git branch --show-current)"
read -p "Переключиться на другую ветку? (оставьте пустым для текущей): " BRANCH
if [ ! -z "$BRANCH" ]; then
    log_info "Переключение на ветку $BRANCH..."
    git checkout "$BRANCH"
fi

# Шаг 6: Создание виртуального окружения
log_info "Создание виртуального окружения..."
python3.11 -m venv venv

# Активация виртуального окружения
log_info "Активация виртуального окружения..."
source venv/bin/activate

# Обновление pip
log_info "Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
log_info "Установка зависимостей из requirements.txt..."
pip install -r requirements.txt

# Шаг 7: Создание .env файла
log_info "Настройка конфигурации..."

if [ ! -f .env ]; then
    log_info "Создание .env файла..."
    cat > .env << 'ENVEOF'
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
ENVEOF
    
    log_warn "Файл .env создан. НЕОБХОДИМО настроить API ключи!"
    echo ""
    read -p "Открыть .env для редактирования сейчас? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
else
    log_info "Файл .env уже существует"
fi

# Шаг 8: Создание systemd сервиса
log_info "Создание systemd сервиса..."

cat > /etc/systemd/system/bybit-api.service << SERVICEEOF
[Unit]
Description=Bybit Trading Bot API Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/run_api.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Шаг 9: Настройка прав доступа
log_info "Настройка прав доступа..."
chmod +x "$INSTALL_DIR/run_api.py"
chown -R root:root "$INSTALL_DIR"

# Шаг 10: Запуск сервиса
log_info "Настройка systemd сервиса..."
systemctl daemon-reload
systemctl enable bybit-api.service

echo ""
echo "================================================"
log_info "Развертывание завершено!"
echo "================================================"
echo ""
echo "Следующие шаги:"
echo "1. Убедитесь, что API ключи настроены в файле .env"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Запустите сервис:"
echo "   systemctl start bybit-api.service"
echo ""
echo "3. Проверьте статус:"
echo "   systemctl status bybit-api.service"
echo ""
echo "4. Просмотрите логи:"
echo "   journalctl -u bybit-api.service -f"
echo ""
echo "5. Проверьте доступность API:"
echo "   curl http://localhost:8000/api/status"
echo ""
echo "Веб-интерфейс будет доступен по адресу: http://45.8.251.77:8000"
echo ""

# Опция автоматического запуска
read -p "Запустить сервис сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Запуск сервиса..."
    systemctl start bybit-api.service
    sleep 2
    systemctl status bybit-api.service
    
    log_info "Проверка API..."
    sleep 3
    curl -s http://localhost:8000/api/status || log_warn "API еще не отвечает, проверьте логи"
fi

echo ""
log_info "Готово!"
