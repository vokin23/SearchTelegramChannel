#!/bin/bash

# Быстрое развертывание Telegram Channel Search Bot
echo "🚀 Быстрое развертывание Telegram Channel Search Bot"

# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем зависимости
apt install -y python3 python3-pip python3-venv git nano

# Создаем директорию
mkdir -p /opt/telegram-bot
cd /opt/telegram-bot

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем Python пакеты
pip install --upgrade pip
pip install python-telegram-bot==20.7 telethon==1.34.0 python-dotenv==1.0.0 nest-asyncio==1.5.8 cryptg==0.4.0

echo "✅ Окружение готово! Теперь создайте файлы bot.py и .env"
