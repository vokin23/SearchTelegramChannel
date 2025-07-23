# 🔍 Telegram Channel Search Bot

Бот для поиска Telegram каналов с красивой пагинацией и удобным интерфейсом.

## ✨ Возможности

- 🔍 Поиск каналов по ключевым словам
- 📄 Удобная пагинация результатов
- 👥 Отображение количества подписчиков
- ℹ️ Подробная информация о каналах
- 🎨 Красивый дизайн с эмодзи
- 🔐 Безопасная аутентификация через Telegram API

## 🚀 Быстрое развертывание

### Автоматическая установка на Ubuntu/Debian сервер:

```bash
curl -sSL https://raw.githubusercontent.com/vokin23/SearchTelegramChannel/main/install.sh | bash
```

### Ручная установка:

1. **Клонируйте репозиторий:**
```bash
git clone https://github.com/vokin23/SearchTelegramChannel.git /opt/telegram-bot
cd /opt/telegram-bot
```

2. **Запустите скрипт установки:**
```bash
chmod +x install.sh
./install.sh
```

3. **Настройте переменные окружения:**
```bash
cp .env.example .env
nano .env
```

4. **Запустите бота:**
```bash
systemctl start telegram-bot
systemctl enable telegram-bot
```

## ⚙️ Конфигурация

Создайте файл `.env` с следующими параметрами:

```env
# Telegram API данные (получите на https://my.telegram.org/)
API_ID=your_api_id
API_HASH=your_api_hash

# Токен бота (получите у @BotFather)
BOT_TOKEN=your_bot_token

# Максимальное количество результатов
MAX_RESULTS=100

# Номер телефона администратора (в международном формате)
PHONE_NUMBER=+1234567890
```

## 📋 Требования

- Python 3.8+
- Ubuntu/Debian сервер
- Telegram API ключи
- Telegram Bot Token

## 🛠️ Управление сервисом

```bash
# Статус бота
systemctl status telegram-bot

# Просмотр логов
journalctl -u telegram-bot -f

# Перезапуск
systemctl restart telegram-bot

# Остановка
systemctl stop telegram-bot
```

## 🔧 Разработка

```bash
# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Запустите бота локально
python bot.py
```

## 📝 Получение API ключей

1. **Telegram API (API_ID и API_HASH):**
   - Перейдите на https://my.telegram.org/
   - Войдите в свой аккаунт
   - Создайте новое приложение
   - Скопируйте API ID и API Hash

2. **Bot Token:**
   - Найдите @BotFather в Telegram
   - Создайте нового бота командой `/newbot`
   - Скопируйте полученный токен

## 🐛 Устранение неполадок

### Бот не запускается:
```bash
journalctl -u telegram-bot --no-pager -l
```

### Проблемы с аутентификацией:
```bash
rm /opt/telegram-bot/session_*.session
systemctl restart telegram-bot
```

### Обновление бота:
```bash
cd /opt/telegram-bot
git pull
systemctl restart telegram-bot
```

## 📄 Лицензия

MIT License

## 🤝 Поддержка

Если у вас есть вопросы или предложения, создайте Issue в этом репозитории.

## 📞 Контакты

GitHub: [@vokin23](https://github.com/vokin23)
