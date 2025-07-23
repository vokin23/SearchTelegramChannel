#!/bin/bash

# Скрипт для развертывания Telegram бота на сервере
echo "🚀 Начинаю развертывание Telegram бота..."

# Обновляем систему
echo "📦 Обновляю систему..."
apt update && apt upgrade -y

# Устанавливаем Python 3.9+ и pip
echo "🐍 Устанавливаю Python и зависимости..."
apt install -y python3 python3-pip python3-venv git nano screen

# Создаем директорию для проекта
echo "📁 Создаю директорию проекта..."
mkdir -p /opt/telegram-bot
cd /opt/telegram-bot

# Создаем виртуальное окружение
echo "🔧 Создаю виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
echo "📋 Устанавливаю зависимости Python..."
pip install --upgrade pip
pip install python-telegram-bot==20.7 telethon==1.34.0 python-dotenv==1.0.0 nest-asyncio==1.5.8 cryptg==0.4.0

# Создаем systemd сервис
echo "⚙️ Создаю systemd сервис..."
cat > /etc/systemd/system/telegram-bot.service << EOF
[Unit]
Description=Telegram Channel Search Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-bot
Environment=PATH=/opt/telegram-bot/venv/bin
ExecStart=/opt/telegram-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
systemctl daemon-reload

echo "✅ Развертывание завершено!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Скопируйте файлы bot.py и .env в /opt/telegram-bot/"
echo "2. Запустите бота: systemctl start telegram-bot"
echo "3. Включите автозапуск: systemctl enable telegram-bot"
echo "4. Проверьте статус: systemctl status telegram-bot"
echo "5. Просмотр логов: journalctl -u telegram-bot -f"
