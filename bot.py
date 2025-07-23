import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telethon.sync import TelegramClient
from telethon.tl.functions.contacts import SearchRequest

# Обрабатываем возможные конфликты циклов событий между Telethon и python-telegram-bot
import nest_asyncio
nest_asyncio.apply()

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SEARCH_TERMS = 0
PHONE_NUMBER = 1
VERIFICATION_CODE = 2

# Получение API данных из переменных окружения
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
MAX_RESULTS = int(os.getenv('MAX_RESULTS', '100'))
ADMIN_PHONE = os.getenv('PHONE_NUMBER', '')

# Глобальные переменные
AUTH_DATA = {}
CLIENT = None

# Функция для получения клиента Telethon (синглтон)
async def get_telethon_client(phone_number):
    global CLIENT
    if CLIENT is None or not CLIENT.is_connected():
        CLIENT = TelegramClient('session_' + phone_number, API_ID, API_HASH)
        await CLIENT.connect()
    return CLIENT

# Функция для аутентификации в Telethon
async def authenticate_telethon(phone_number):
    client = await get_telethon_client(phone_number)
    if not await client.is_user_authorized():
        result = await client.send_code_request(phone_number)
        AUTH_DATA[phone_number] = {'phone_code_hash': result.phone_code_hash}
        logger.info(f"Запрошен код подтверждения для номера {phone_number}")
        return client, False
    logger.info(f"Пользователь {phone_number} уже авторизован")
    return client, True

# Функция для завершения аутентификации с кодом
async def complete_authentication(phone_number, code):
    client = await get_telethon_client(phone_number)
    try:
        if phone_number in AUTH_DATA and 'phone_code_hash' in AUTH_DATA[phone_number]:
            phone_code_hash = AUTH_DATA[phone_number]['phone_code_hash']
            await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            AUTH_DATA.pop(phone_number, None)
            return True
        else:
            if await client.is_user_authorized():
                return True
            return False
    except Exception as e:
        logger.error(f"Ошибка при аутентификации: {e}")
        return False

# Функция для поиска каналов через Telethon API
async def search_channels(search_terms, phone_number):
    results = []
    logger.info(f"Начинаю поиск каналов по ключевым словам: {search_terms}")

    client = await get_telethon_client(phone_number)

    if not await client.is_user_authorized():
        logger.info("Пользователь не авторизован, требуется аутентификация")
        return "auth_required"

    try:
        # Поиск через глобальный поиск Telegram
        for term in search_terms:
            logger.info(f"Выполняю поиск по запросу: {term}")
            try:
                search_result = await client(SearchRequest(
                    q=term,
                    limit=50
                ))

                for chat in search_result.chats:
                    if hasattr(chat, 'username') and chat.username and hasattr(chat, 'broadcast') and chat.broadcast:
                        channel_info = {
                            'title': chat.title,
                            'username': chat.username,
                            'link': f'https://t.me/{chat.username}',
                            'description': getattr(chat, 'about', 'Нет описания'),
                            'participants_count': getattr(chat, 'participants_count', 0)
                        }

                        # Проверяем, нет ли уже такого канала в результатах
                        if not any(r['username'] == channel_info['username'] for r in results):
                            results.append(channel_info)

                        if len(results) >= MAX_RESULTS:
                            break
            except Exception as e:
                logger.error(f"Ошибка при поиске по термину {term}: {e}")
                continue

            if len(results) >= MAX_RESULTS:
                break

        # Дополнительный поиск в диалогах пользователя
        if len(results) < MAX_RESULTS:
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if hasattr(entity, 'broadcast') and entity.broadcast and hasattr(entity, 'username') and entity.username:
                    # Проверяем релевантность
                    relevant = False
                    for term in search_terms:
                        if (term.lower() in entity.title.lower() or
                            (hasattr(entity, 'about') and entity.about and term.lower() in entity.about.lower())):
                            relevant = True
                            break

                    if relevant:
                        channel_info = {
                            'title': entity.title,
                            'username': entity.username,
                            'link': f'https://t.me/{entity.username}',
                            'description': getattr(entity, 'about', 'Нет описания'),
                            'participants_count': getattr(entity, 'participants_count', 0)
                        }

                        if not any(r['username'] == channel_info['username'] for r in results):
                            results.append(channel_info)

                        if len(results) >= MAX_RESULTS:
                            break

        logger.info(f"Поиск завершен. Найдено каналов: {len(results)}")
    except Exception as e:
        logger.error(f"Ошибка при поиске каналов: {e}")
        return "error"

    return results

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    welcome_message = (
        "🎉 *Добро пожаловать в поиск Telegram каналов!* 🎉\n\n"
        f"Привет, {user.mention_html()}! 👋\n\n"
        "🔍 *Как это работает:*\n"
        "• Отправьте мне ключевые слова через запятую\n"
        "• Я найду для вас интересные каналы\n"
        "• Используйте кнопки для навигации по результатам\n\n"
        "📝 *Пример запроса:*\n"
        "`программирование, технологии, новости`\n\n"
        "💡 *Совет:* Чем конкретнее термины, тем лучше результаты!\n\n"
        "🚀 Готовы начать? Отправьте ваш поисковый запрос!"
    )

    await update.message.reply_html(welcome_message)
    return SEARCH_TERMS

# Обработчик получения поисковых терминов
async def get_search_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    search_terms = [term.strip() for term in text.split(',') if term.strip()]

    if not search_terms:
        error_message = (
            "❌ *Некорректный запрос*\n\n"
            "📝 Пожалуйста, отправьте хотя бы одно ключевое слово\n\n"
            "💡 *Пример:* `новости, спорт, технологии`\n"
            "🔄 Разделяйте запросы запятыми"
        )
        await update.message.reply_html(error_message)
        return SEARCH_TERMS

    context.user_data['search_terms'] = search_terms

    # Красивое сообщение о начале поиска
    search_message = (
        "🔍 *Запускаю поиск каналов...*\n\n"
        f"🎯 *Поисковые термины:* `{', '.join(search_terms)}`\n\n"
        "⏳ Это может занять до минуты, пожалуйста подождите...\n"
        "🔄 Сканирую базу Telegram каналов..."
    )
    search_msg = await update.message.reply_html(search_message)

    phone_number = ADMIN_PHONE
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    results = await search_channels(search_terms, phone_number)

    # Удаляем сообщение о поиске
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=search_msg.message_id)
    except:
        pass

    if results == "auth_required":
        auth_message = (
            "🔐 *Требуется аутентификация*\n\n"
            "📱 Для доступа к API Telegram нужно подтвердить админский аккаунт\n"
            "💬 Отправьте код подтверждения из SMS"
        )
        await update.message.reply_html(auth_message)
        context.user_data['phone_number'] = phone_number
        client, auth_status = await authenticate_telethon(phone_number)
        return VERIFICATION_CODE
    elif results == "error":
        error_message = (
            "⚠️ *Произошла ошибка при поиске*\n\n"
            "🔄 Попробуйте еще раз позже\n"
            "💡 Или измените поисковые запросы"
        )
        await update.message.reply_html(error_message)
        return SEARCH_TERMS

    if not results:
        no_results_message = (
            "😔 *Каналы не найдены*\n\n"
            f"🔍 По запросу `{', '.join(search_terms)}` ничего не найдено\n\n"
            "💡 *Попробуйте:*\n"
            "• Использовать более общие термины\n"
            "• Проверить правописание\n"
            "• Попробовать английские термины\n\n"
            "🔄 Введите новый поисковый запрос"
        )
        await update.message.reply_html(no_results_message)
    else:
        context.user_data['search_results'] = results
        await show_channels_buttons(update, context)

    return SEARCH_TERMS

# Функция для отображения каналов с пагинацией
async def show_channels_buttons(update, context):
    results = context.user_data.get('search_results', [])

    if not results:
        await update.message.reply_html("❌ Нет результатов для отображения")
        return

    if 'buttons_page' not in context.user_data:
        context.user_data['buttons_page'] = 0

    page = context.user_data['buttons_page']
    channels_per_page = 6
    total_pages = (len(results) + channels_per_page - 1) // channels_per_page

    start_idx = page * channels_per_page
    end_idx = min(start_idx + channels_per_page, len(results))
    current_channels = results[start_idx:end_idx]

    # Красивое сообщение с результатами
    message_text = (
        f"🎉 *Найдено {len(results)} каналов!*\n\n"
        f"📄 Страница {page + 1} из {total_pages}\n"
        f"🔽 Выберите канал для перехода:"
    )

    keyboard = []

    # Кнопки каналов
    for i, channel in enumerate(current_channels, 1):
        title = channel['title']
        if len(title) > 35:
            title = title[:35] + "..."

        # Добавляем информацию о подписчиках если есть
        subscribers_info = ""
        if channel.get('participants_count', 0) > 0:
            count = channel['participants_count']
            if count >= 1000000:
                subscribers_info = f" ({count//1000000}M)"
            elif count >= 1000:
                subscribers_info = f" ({count//1000}K)"
            else:
                subscribers_info = f" ({count})"

        button_text = f"{start_idx + i}. 📢 {title}{subscribers_info}"
        keyboard.append([InlineKeyboardButton(button_text, url=channel['link'])])

    # Разделительная линия
    keyboard.append([InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="ignore")])

    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))

    nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="ignore"))

    if end_idx < len(results):
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data="next_page"))

    keyboard.append(nav_buttons)

    # Дополнительные кнопки
    keyboard.append([
        InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search"),
        InlineKeyboardButton("ℹ️ Подробнее", callback_data="detailed_view")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if hasattr(update, 'message') and update.message:
            message = await update.message.reply_html(message_text, reply_markup=reply_markup)
        else:
            message = await context.bot.edit_message_text(
                message_text,
                chat_id=update.effective_chat.id,
                message_id=context.user_data.get('results_message_id'),
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

        if hasattr(update, 'message') and update.message:
            context.user_data['results_message_id'] = message.message_id
            context.user_data['chat_id'] = update.effective_chat.id

    except Exception as e:
        logger.error(f"Ошибка при отображении каналов: {e}")

# Обработчик callback'ов для пагинации
async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "prev_page":
        context.user_data['buttons_page'] = max(0, context.user_data.get('buttons_page', 0) - 1)
        await show_channels_buttons(query, context)

    elif query.data == "next_page":
        results = context.user_data.get('search_results', [])
        channels_per_page = 6
        max_page = (len(results) - 1) // channels_per_page
        context.user_data['buttons_page'] = min(max_page, context.user_data.get('buttons_page', 0) + 1)
        await show_channels_buttons(query, context)

    elif query.data == "new_search":
        context.user_data.clear()
        welcome_msg = (
            "🔍 *Новый поиск*\n\n"
            "Введите новые ключевые слова для поиска каналов:"
        )
        await query.edit_message_text(welcome_msg, parse_mode='HTML')
        return SEARCH_TERMS

    elif query.data == "detailed_view":
        await show_detailed_results(query, context)

    elif query.data == "ignore":
        pass

# Показать подробные результаты
async def show_detailed_results(query, context):
    results = context.user_data.get('search_results', [])
    page = context.user_data.get('buttons_page', 0)
    channels_per_page = 6

    start_idx = page * channels_per_page
    end_idx = min(start_idx + channels_per_page, len(results))
    current_channels = results[start_idx:end_idx]

    message_text = f"📊 *Подробная информация (страница {page + 1}):*\n\n"

    for i, channel in enumerate(current_channels, 1):
        message_text += f"**{start_idx + i}. {channel['title']}**\n"
        message_text += f"👥 Подписчиков: {channel.get('participants_count', 'Неизвестно')}\n"
        message_text += f"📝 Описание: {channel['description'][:100]}{'...' if len(channel['description']) > 100 else ''}\n"
        message_text += f"🔗 Ссылка: {channel['link']}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')

# Обработчик кода верификации
async def get_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip()
    phone_number = context.user_data.get('phone_number')

    if not phone_number:
        await update.message.reply_html("❌ Ошибка: номер телефона не найден. Начните заново с /start")
        return SEARCH_TERMS

    success = await complete_authentication(phone_number, code)

    if success:
        await update.message.reply_html("✅ Успешная авторизация! Повторяю поиск...")

        # Повторяем поиск после авторизации
        search_terms = context.user_data.get('search_terms', [])
        if search_terms:
            results = await search_channels(search_terms, phone_number)
            if results and results != "error":
                context.user_data['search_results'] = results
                await show_channels_buttons(update, context)
            else:
                await update.message.reply_html("😔 Каналы не найдены")

        return SEARCH_TERMS
    else:
        await update.message.reply_html(
            "❌ Неверный код. Попробуйте еще раз или начните заново с /start"
        )
        return VERIFICATION_CODE

# Обработчик отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_html("❌ Поиск отменен. Используйте /start для нового поиска.")
    return ConversationHandler.END

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEARCH_TERMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_search_terms)],
            VERIFICATION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_verification_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_pagination))

    # Запускаем бота
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
