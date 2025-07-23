#!/bin/bash

# Автоматическая установка Telegram Channel Search Bot
# Использование: curl -sSL https://raw.githubusercontent.com/vokin23/SearchTelegramChannel/main/install.sh | bash

set -e

echo "🚀 Автоматическая установка Telegram Channel Search Bot"
echo "=================================================="

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Пожалуйста, запустите скрипт от имени root или с sudo"
    exit 1
fi

# Обновляем систему
echo "📦 Обновляю систему..."
apt update && apt upgrade -y

# Устанавливаем необходимые пакеты
echo "🔧 Устанавливаю зависимости..."
apt install -y python3 python3-pip python3-venv git nano screen curl

# Создаем пользователя для бота (безопасность)
echo "👤 Создаю пользователя для бота..."
if ! id "telegrambot" &>/dev/null; then
    useradd -r -s /bin/false -d /opt/telegram-bot telegrambot
fi

# Удаляем старую установку если есть
if [ -d "/opt/telegram-bot" ]; then
    echo "🗑️ Удаляю старую установку..."
    systemctl stop telegram-bot 2>/dev/null || true
    rm -rf /opt/telegram-bot
fi

# Клонируем репозиторий
echo "📥 Клонирую репозиторий..."
git clone https://github.com/vokin23/SearchTelegramChannel.git /opt/telegram-bot
cd /opt/telegram-bot

# Создаем виртуальное окружение
echo "🐍 Создаю виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости Python
echo "📋 Устанавливаю зависимости Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Создаем файл конфигурации из примера
echo "⚙️ Создаю файл конфигурации..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Файл .env создан. Не забудьте его настроить!"
fi

# Устанавливаем права доступа
echo "🔒 Настраиваю права доступа..."
chown -R telegrambot:telegrambot /opt/telegram-bot
chmod +x /opt/telegram-bot/venv/bin/python

# Создаем systemd сервис
echo "⚙️ Создаю systemd сервис..."
cat > /etc/systemd/system/telegram-bot.service << 'EOF'
[Unit]
Description=Telegram Channel Search Bot
After=network.target

[Service]
Type=simple
User=telegrambot
Group=telegrambot
WorkingDirectory=/opt/telegram-bot
Environment=PATH=/opt/telegram-bot/venv/bin
ExecStart=/opt/telegram-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
systemctl daemon-reload

# Создаем скрипты управления
echo "📝 Создаю скрипты управления..."
cat > /usr/local/bin/telegram-bot << 'EOF'
#!/bin/bash
case "$1" in
    start)
        systemctl start telegram-bot
        ;;
    stop)
        systemctl stop telegram-bot
        ;;
    restart)
        systemctl restart telegram-bot
        ;;
    status)
        systemctl status telegram-bot
        ;;
    logs)
        journalctl -u telegram-bot -f
        ;;
    update)
        cd /opt/telegram-bot
        git pull
        systemctl restart telegram-bot
        echo "✅ Бот обновлен и перезапущен"
        ;;
    config)
        nano /opt/telegram-bot/.env
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs|update|config}"
        exit 1
        ;;
esac
EOF

chmod +x /usr/local/bin/telegram-bot

echo ""
echo "✅ Установка завершена успешно!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Настройте конфигурацию: telegram-bot config"
echo "2. Запустите бота: telegram-bot start"
echo "3. Включите автозапуск: systemctl enable telegram-bot"
echo "4. Проверьте статус: telegram-bot status"
echo ""
echo "🔧 Доступные команды:"
echo "  telegram-bot start    - Запустить бота"
echo "  telegram-bot stop     - Остановить бота"
echo "  telegram-bot restart  - Перезапустить бота"
echo "  telegram-bot status   - Показать статус"
echo "  telegram-bot logs     - Показать логи"
echo "  telegram-bot update   - Обновить бота"
echo "  telegram-bot config   - Редактировать конфигурацию"
echo ""
echo "📖 Документация: https://github.com/vokin23/SearchTelegramChannel"
