import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telethon.sync import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import InputPeerEmpty

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
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
MAX_RESULTS = int(os.getenv('MAX_RESULTS', 10))
ADMIN_PHONE = os.getenv('PHONE_NUMBER')  # Получаем номер телефона из .env

# Глобальная переменная для хранения номера телефона в процессе аутентификации
PHONE_TO_AUTH = {}

# Глобальная переменная для хранения данных аутентификации
AUTH_DATA = {}

# Глобальная переменная для хранения экземпляра клиента Telethon
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
        # Запрашиваем код и сохраняем phone_code_hash
        result = await client.send_code_request(phone_number)
        # Сохраняем phone_code_hash для последующей аутентификации
        AUTH_DATA[phone_number] = {'phone_code_hash': result.phone_code_hash}
        logger.info(f"Запрошен код подтверждения для номера {phone_number}")
        return client, False

    logger.info(f"Пользователь {phone_number} уже авторизован")
    return client, True

# Функция для завершения аутентификации с кодом
async def complete_authentication(phone_number, code):
    client = await get_telethon_client(phone_number)

    try:
        # Проверяем, есть ли сохраненный phone_code_hash
        if phone_number in AUTH_DATA and 'phone_code_hash' in AUTH_DATA[phone_number]:
            phone_code_hash = AUTH_DATA[phone_number]['phone_code_hash']
            logger.info(f"Использую сохраненный phone_code_hash для номера {phone_number}")
            # Используем phone_code_hash при входе
            await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            # Очищаем данные после успешной аутентификации
            AUTH_DATA.pop(phone_number, None)
            return True
        else:
            # Если хеша нет, пробуем войти без него (для уже авторизованных сессий)
            if await client.is_user_authorized():
                logger.info(f"Пользователь {phone_number} уже авторизован")
                return True

            logger.error(f"Отсутствует phone_code_hash для номера {phone_number}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при аутентификации: {e}")
        return False

# Функция для поиска каналов через Telethon API
async def search_channels(search_terms, phone_number):
    results = []
    logger.info(f"Начинаю поиск каналов по ключевым словам: {search_terms}")

    # Получаем единый экземпляр клиента Telethon
    client = await get_telethon_client(phone_number)

    # Проверяем авторизацию
    if not await client.is_user_authorized():
        logger.info("Пользователь не авторизован, требуется аутентификация")
        return "auth_required"

    try:
        # Используем более эффективный метод поиска через функцию client.get_dialogs
        channels_checked = 0
        logger.info("Получаю список диалогов...")

        # Сначала ищем по глобальному поиску Telegram
        for term in search_terms:
            logger.info(f"Выполняю глобальный поиск по запросу: {term}")
            # Используем встроенную функцию поиска Telethon
            async for result in client.iter_messages(None, search=term, limit=100):
                if result.chat and hasattr(result.chat, 'username') and result.chat.username:
                    try:
                        # Проверяем, является ли чат каналом
                        entity = await client.get_entity(result.chat.username)

                        if hasattr(entity, 'broadcast'):  # Это канал
                            channel_info = {
                                'title': entity.title,
                                'username': entity.username,
                                'link': f'https://t.me/{entity.username}',
                                'description': getattr(entity, 'about', 'Нет описания')
                            }

                            # Проверяем, нет ли уже такого канала в результатах
                            if not any(r['username'] == channel_info['username'] for r in results):
                                logger.info(f"Найден канал: {channel_info['title']}")
                                results.append(channel_info)
                                channels_checked += 1

                                # Если достигли лимита результатов, останавливаемся
                                if len(results) >= MAX_RESULTS:
                                    break
                    except Exception as e:
                        logger.error(f"Ошибка при получении информации о канале: {e}")
                        continue

            if len(results) >= MAX_RESULTS:
                break

        # Если мы нашли хотя бы один канал через глобальный поиск, но хотим больше
        if 0 < len(results) < MAX_RESULTS:
            logger.info("Ищу дополнительные каналы в списке диалогов...")
            # Получаем все диалоги пользователя
            async for dialog in client.iter_dialogs():
                entity = dialog.entity

                # Проверяем, является ли сущность каналом и имеет ли username
                if hasattr(entity, 'broadcast') and hasattr(entity, 'username') and entity.username:
                    channel_info = {
                        'title': entity.title,
                        'username': entity.username,
                        'link': f'https://t.me/{entity.username}',
                        'description': getattr(entity, 'about', 'Нет описания')
                    }

                    # Проверяем релевантность канала для поисковых терминов
                    relevant = False
                    for term in search_terms:
                        # Проверяем наличие поискового термина в названии или описании
                        if (term.lower() in channel_info['title'].lower() or
                            (channel_info['description'] and term.lower() in channel_info['description'].lower())):
                            relevant = True
                            break

                        # Проверяем частичные совпадения слов
                        title_words = channel_info['title'].lower().split()
                        desc_words = channel_info['description'].lower().split() if channel_info['description'] else []

                        for word in title_words + desc_words:
                            if (len(word) >= 4 and (word in term.lower() or term.lower() in word)):
                                relevant = True
                                break

                        if relevant:
                            break

                    # Если канал релевантен и его еще нет в результатах, добавляем
                    if relevant and not any(r['username'] == channel_info['username'] for r in results):
                        logger.info(f"Найден релевантный канал: {channel_info['title']}")
                        results.append(channel_info)

                        # Если достигли лимита результатов, останавливаемся
                        if len(results) >= MAX_RESULTS:
                            break

        # Если все еще не нашли каналы, попробуем прямой поиск по каналам через TL-методы
        if len(results) == 0:
            logger.info("Пробую прямой поиск по каналам...")
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.tl.types import InputPeerEmpty

            for term in search_terms:
                search_result = await client(SearchRequest(
                    q=term,
                    limit=MAX_RESULTS
                ))

                for chat in search_result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        try:
                            channel_info = {
                                'title': chat.title,
                                'username': chat.username,
                                'link': f'https://t.me/{chat.username}',
                                'description': getattr(chat, 'about', 'Нет описания')
                            }

                            # Проверяем, нет ли уже такого канала в результатах
                            if not any(r['username'] == channel_info['username'] for r in results):
                                logger.info(f"Найден канал через прямой поиск: {channel_info['title']}")
                                results.append(channel_info)

                                # Если достигли лимита результатов, останавливаемся
                                if len(results) >= MAX_RESULTS:
                                    break
                        except Exception as e:
                            logger.error(f"Ошибка при получении информации о канале: {e}")
                            continue

        logger.info(f"Поиск завершен. Найдено каналов: {len(results)}")
    except Exception as e:
        logger.error(f"Ошибка при поиске каналов: {e}")
        return "error"

    return results

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    welcome_message = (
        "🎉 *Добро пожаловать!* 🎉\n\n"
        f"Привет, {user.mention_html()}! 👋\n\n"
        "🔍 *Я — бот для поиска Telegram каналов*\n"
        "Отправьте мне ключевые слова через запятую, и я найду для вас интересные каналы!\n\n"
        "📝 *Пример запроса:*\n"
        "`новости, спорт, технологии`\n\n"
        "💡 *Совет:* Используйте конкретные термины для лучших результатов"
    )

    await update.message.reply_html(welcome_message)
    return SEARCH_TERMS

# Обработчик получения поисковых терминов
async def get_search_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Получаем текст сообщения и разбиваем его на отдельные слова/фразы
    text = update.message.text
    search_terms = [term.strip() for term in text.split(',') if term.strip()]

    if not search_terms:
        error_message = (
            "❌ *Упс! Что-то пошло не так*\n\n"
            "📝 Пожалуйста, отправьте мне хотя бы одно ключевое слово для поиска\n\n"
            "💡 *Пример:* `новости, спорт, технологии`\n"
            "🔄 Разделяйте несколько запросов запятыми"
        )
        await update.message.reply_html(error_message)
        return SEARCH_TERMS

    # Сохраняем поисковые термины в контексте пользователя
    context.user_data['search_terms'] = search_terms

    search_message = (
        "🔍 *Начинаю поиск каналов...*\n\n"
        f"🎯 *Ключевые слова:* `{', '.join(search_terms)}`\n\n"
        "⏳ Это может занять некоторое время, пожалуйста подождите..."
    )
    await update.message.reply_html(search_message)

    # Используем номер телефона из .env файла
    phone_number = ADMIN_PHONE

    # Асинхронный поиск каналов
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # Запуск асинхронного поиска без asyncio.run()
    results = await search_channels(search_terms, phone_number)

    # Обработка результатов поиска
    if results == "auth_required":
        auth_message = (
            "🔐 *Требуется аутентификация*\n\n"
            "📱 Для работы с API Telegram необходимо подтвердить административный аккаунт\n"
            "💬 Отправьте код подтверждения, который придет в SMS"
        )
        await update.message.reply_html(auth_message)
        # Сохраняем номер телефона администратора в контексте пользователя
        context.user_data['phone_number'] = phone_number
        # Запрашиваем код аутентификации без asyncio.run()
        client, auth_status = await authenticate_telethon(phone_number)
        return VERIFICATION_CODE
    elif results == "error":
        error_message = (
            "⚠️ *Произошла ошибка при поиске*\n\n"
            "🔄 Пожалуйста, попробуйте еще раз позже\n"
            "💡 Или попробуйте изменить поисковые запросы"
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
            "• Попробовать синонимы\n\n"
            "🔄 Введите новый поисковый запрос"
        )
        await update.message.reply_html(no_results_message)
    else:
        # Сохраняем результаты поиска в контексте пользователя
        context.user_data['search_results'] = results

        # Отображаем каналы в виде кнопок (вместо пагинации)
        await show_channels_buttons(update, context)

    return SEARCH_TERMS

# Функция для отображения страницы с каналами
async def show_channels_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    current_page = context.user_data.get('current_page', 0)

    if not results:
        await update.message.reply_text("Нет результатов для отображения.")
        return

    # Получаем текущий канал для отображения
    channel = results[current_page]
    total_channels = len(results)

    # Экранируем специальные символы Markdown
    title = channel['title'].replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[')
    description = "Нет описания"
    if channel['description']:
        description = channel['description'].replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[')

    # Формируем сообщение с текущим каналом
    message_text = (
        f"📢 *{title}*\n\n"
        f"📝 *Описание:* {description}\n\n"
        f"🔗 *Ссылка:* {channel['link']}\n\n"
        f"Канал {current_page + 1} из {total_channels}"
    )

    # Создаем кнопки навигации
    keyboard = []
    buttons_row = []

    # Кнопка "Предыдущий" (если не на первой странице)
    if current_page > 0:
        buttons_row.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_channel"))

    # Кнопка перехода на канал
    buttons_row.append(InlineKeyboardButton("Перейти на канал", url=channel['link']))

    # Кнопка "Следующий" (если не на последней странице)
    if current_page < total_channels - 1:
        buttons_row.append(InlineKeyboardButton("Вперёд ➡️", callback_data="next_channel"))

    keyboard.append(buttons_row)
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Если это первое сообщение с результатами, отправляем новое
        if 'results_message_id' not in context.user_data:
            message = await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            context.user_data['results_message_id'] = message.message_id
            context.user_data['chat_id'] = update.effective_chat.id
        else:
            # Иначе редактируем существующее сообщение
            await context.bot.edit_message_text(
                message_text,
                chat_id=context.user_data['chat_id'],
                message_id=context.user_data['results_message_id'],
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения о канале: {e}")
        # Отправляем без форматирования в случае ошибки
        try:
            if 'results_message_id' not in context.user_data:
                message = await update.message.reply_text(
                    f"📢 {title}\n\n"
                    f"📝 Описание: {description}\n\n"
                    f"🔗 Ссылка: {channel['link']}\n\n"
                    f"Канал {current_page + 1} из {total_channels}",
                    reply_markup=reply_markup
                )
                context.user_data['results_message_id'] = message.message_id
                context.user_data['chat_id'] = update.effective_chat.id
            else:
                await context.bot.edit_message_text(
                    f"📢 {title}\n\n"
                    f"📝 Описание: {description}\n\n"
                    f"🔗 Ссылка: {channel['link']}\n\n"
                    f"Канал {current_page + 1} из {total_channels}",
                    chat_id=context.user_data['chat_id'],
                    message_id=context.user_data['results_message_id'],
                    reply_markup=reply_markup
                )
        except Exception as e2:
            logger.error(f"Повторная ошибка при отправке сообщения о канале: {e2}")

# Функция для отображения каналов в виде кнопок с пагинацией
async def show_channels_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])

    if not results:
        no_results_message = (
            "❌ *Результаты не найдены*\n\n"
            "😔 К сожалению, нет каналов для отображения\n"
            "🔄 Попробуйте начать новый поиск с /start"
        )
        await update.message.reply_html(no_results_message)
        return

    # Получаем текущую страницу или устанавливаем на 0, если это первый вызов
    if 'buttons_page' not in context.user_data:
        context.user_data['buttons_page'] = 0

    page = context.user_data['buttons_page']
    total_results = len(results)
    channels_per_page = 8  # Уменьшим до 8 каналов на странице для лучшего отображения
    total_pages = (total_results + channels_per_page - 1) // channels_per_page

    # Вычисляем начальный и конечный индекс для текущей страницы
    start_idx = page * channels_per_page
    end_idx = min(start_idx + channels_per_page, total_results)

    # Получаем каналы для текущей страницы
    current_page_channels = results[start_idx:end_idx]

    # Формируем красивое сообщение с результатами
    message_text = (
        f"🎉 *Найдено {total_results} каналов!*\n\n"
        f"📄 Страница {page + 1} из {total_pages}\n"
        f"👆 Нажмите на канал, чтобы перейти к нему"
    )

    # Создаем кнопки с названиями каналов
    keyboard = []
    for i, channel in enumerate(current_page_channels, 1):
        # Получаем название канала, ограничиваем его длину
        title = channel['title']
        if len(title) > 32:  # Ограничиваем длину названия
            title = title[:32] + "..."

        # Создаем кнопку для канала с номером
        channel_button = InlineKeyboardButton(
            f"{start_idx + i}. 📢 {title}",
            url=channel['link']
        )
        keyboard.append([channel_button])

    # Добавляем разделительную линию перед навигацией
    if keyboard:
        keyboard.append([InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="ignore")])

    # Добавляем кнопки навигации
    nav_buttons = []

    # Кнопка "Предыдущая страница" (если не на первой странице)
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))

    # Добавляем красивый индикатор страницы
    nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="ignore"))

    # Кнопка "Следняя страница" (если не на последней странице)
    if end_idx < total_results:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data="next_page"))

    # Добавляем навигационные кнопки в клавиатуру
    if nav_buttons:
        keyboard.append(nav_buttons)

    # Добавляем кнопку "Новый поиск"
    keyboard.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Если это первое сообщение с результатами, отправляем новое
        if 'results_message_id' not in context.user_data:
            message = await update.message.reply_html(
                message_text,
                reply_markup=reply_markup
            )
            context.user_data['results_message_id'] = message.message_id
            context.user_data['chat_id'] = update.effective_chat.id
        else:
            # Иначе редактируем существующее сообщение
            await context.bot.edit_message_text(
                message_text,
                chat_id=context.user_data['chat_id'],
                message_id=context.user_data['results_message_id'],
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке списка каналов: {e}")
        # В случае ошибки пробуем отправить новое сообщение
        try:
            message = await update.message.reply_html(
                message_text,
                reply_markup=reply_markup
            )
            context.user_data['results_message_id'] = message.message_id
            context.user_data['chat_id'] = update.effective_chat.id
        except Exception as e2:
            logger.error(f"Повторная ошибка при отправке списка каналов: {e2}")
            # Если все попытки неудачные, отправляем простой текстовый список
            simple_message = f"🎉 Найдено {total_results} каналов!\n\n"
            for i, channel in enumerate(current_page_channels, start_idx + 1):
                simple_message += f"{i}. 📢 {channel['title']}\n🔗 {channel['link']}\n\n"
            await update.message.reply_text(simple_message)

# Обработчик callback-запросов для пагинации
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Определяем, какая кнопка была нажата
    if query.data == "next_channel":
        # Переход к следующему каналу
        context.user_data['current_page'] += 1
        await show_channels_page(update, context)
    elif query.data == "prev_channel":
        # Переход к предыдущему каналу
        context.user_data['current_page'] -= 1
        await show_channels_page(update, context)
    elif query.data == "next_page":
        # Переход к следующей странице списка каналов
        context.user_data['buttons_page'] += 1
        await show_channels_buttons(update, context)
    elif query.data == "prev_page":
        # Переход к предыдущей странице списка каналов
        context.user_data['buttons_page'] -= 1
        await show_channels_buttons(update, context)
    elif query.data == "ignore":
        # Пустое действие для кнопки-индикатора страницы
        pass
    elif query.data == "new_search":
        # Начать новый поиск
        # Очищаем предыдущие результаты
        context.user_data.clear()
        new_search_message = (
            "🔍 *Новый поиск*\n\n"
            "📝 Введите ключевые слова через запятую для поиска каналов\n\n"
            "💡 *Примеры:*\n"
            "• `новости, политика`\n"
            "• `спорт, футбол`\n"
            "• `технологии, программирование`"
        )
        await query.edit_message_text(
            new_search_message,
            parse_mode='HTML'
        )
    else:
        # Обработка других callback-запросов
        pass

# Обработчик получения номера телефона
async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text.strip()

    # Сохраняем номер телефона в контексте пользователя
    context.user_data['phone_number'] = phone_number

    await update.message.reply_text(
        f"Вы ввели номер телефона: {phone_number}\n"
        f"Отправьте мне код подтверждения, который был выслан на этот номер."
    )

    # Асинхронная аутентификация
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # Запрашиваем код подтверждения
    await authenticate_telethon(phone_number)
    return VERIFICATION_CODE

# Обработчик получения кода подтверждения
async def get_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip()

    phone_number = context.user_data.get('phone_number')
    if not phone_number:
        await update.message.reply_text(
            "Сначала введите номер телефона, на который был выслан код подтверждения."
        )
        return PHONE_NUMBER

    # Завершаем аутентификацию с введенным кодом
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # Проверяем код подтверждения
    is_authenticated = await complete_authentication(phone_number, code)

    if is_authenticated:
        await update.message.reply_text(
            "Аутентификация прошла успешно! Теперь вы можете искать каналы.\n"
            "Отправьте мне слова или фразы через запятую для поиска каналов."
        )
        return SEARCH_TERMS
    else:
        await update.message.reply_text(
            "Не удалось завершить аутентификацию. Пожалуйста, проверьте введенный код и попробуйте снова."
        )
        return ConversationHandler.END

# Функция для отмены поиска
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Поиск отменен. Отправьте /start, чтобы начать новый поиск."
    )
    return ConversationHandler.END

# Основная функция для запуска бота
async def main():
    # Проверка наличия необходимых переменных окружения
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        logger.error("Отсутствуют необходимые переменные окружения. Проверьте файл .env")
        return

    # Создаем Application и передаем ему токен бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем ConversationHandler для управления диалогом
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEARCH_TERMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_search_terms),
            ],
            PHONE_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone_number),
            ],
            VERIFICATION_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_verification_code),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Добавляем ConversationHandler в приложение
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запуск бота
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
