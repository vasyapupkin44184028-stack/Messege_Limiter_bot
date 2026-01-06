from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from datetime import datetime, timedelta
import html
import json

from ..keyboards.admin import (
    get_main_menu_keyboard, 
    get_back_to_menu_keyboard,
    get_settings_keyboard,
    get_exceptions_keyboard,
    get_chats_list_keyboard,
    get_chat_management_keyboard,
    get_exceptions_list_keyboard,
    get_global_settings_keyboard,
    get_user_management_keyboard,
    get_statistics_keyboard,
    get_security_keyboard
)
from ..database import db
from bot.states import AdminStates
from ..config import config
from ..utils.admin_check import is_admin
# В файл callbacks.py, после существующих импортов, добавить:

from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

def safe_format_count(count: int, limit) -> str:
    """Безопасное форматирование счетчика"""
    if limit is None:
        return f"{count}/∞"
    return safe_format_count(count, limit)

@router.message(Command("search_chats"))
async def cmd_search_chats(message: Message, state: FSMContext):
    """Поиск чатов по названию"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    text = (
        "🔍 Поиск чатов\n\n"
        "Отправьте текст для поиска чатов:\n"
        "• Можно искать по названию чата\n"
        "• Или по ID чата (например: -1001234567890)\n\n"
        "❌ Отмена: отправьте 'отмена'"
    )
    
    await message.answer(text, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_chat_search)

# Добавить состояние поиска чатов
@router.message(StateFilter(AdminStates.waiting_for_chat_search))
async def process_chat_search(message: Message, state: FSMContext):
    """Обработка поиска чатов"""
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        return
    
    search_text = message.text.strip()
    
    if search_text.lower() == 'отмена':
        await message.answer("❌ Поиск отменен")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    try:
        if not search_text:
            await message.answer("❌ Введите текст для поиска")
            return
        
        chats = await db.search_chats(search_text)
        
        if chats:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            
            chat_buttons = []
            chat_list = ""
            
            for i, chat in enumerate(chats[:15], 1):
                icon = "👥" if chat.id < -100 else "💬"
                status = "🟢" if chat.is_active else "🔴"
                
                chat_list += (
                    f"{i}. {icon} {status} {chat.title[:25]}\n"
                    f"   ID: <code>{chat.id}</code> • Лимит: {chat.message_limit}\n\n"
                )
                
                chat_buttons.append({
                    "id": chat.id,
                    "title": chat.title[:20],
                    "icon": icon
                })
            
            text = (
                f"🔍 <b>Результаты поиска: \"{search_text}\"</b>\n\n"
                f"📊 Найдено чатов: {len(chats)}\n\n"
                f"{chat_list}"
                f"<i>Выберите чат для управления:</i>"
            )
            
            builder = InlineKeyboardBuilder()
            
            for chat_data in chat_buttons[:10]:
                display_text = f"{chat_data['icon']} {chat_data['title']}"
                if len(display_text) > 25:
                    display_text = display_text[:23] + ".."
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=display_text,
                        callback_data=f"chat_select:{chat_data['id']}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад в меню",
                    callback_data="main_menu"
                ),
                types.InlineKeyboardButton(
                    text="🔄 Новый поиск",
                    callback_data="admin:search_chats"
                ),
                width=2
            )
            
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        else:
            text = (
                f"🔍 <b>Результаты поиска: \"{search_text}\"</b>\n\n"
                f"❌ Чаты не найдены\n\n"
                f"Попробуйте:\n"
                f"1. Другой поисковый запрос\n"
                f"2. Поиск по ID чата (начинается с -100)\n"
                f"3. Посмотреть все чаты в /chats"
            )
            
            from ..keyboards.admin import get_back_to_menu_keyboard
            await message.answer(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {str(e)}")
    
    await state.clear()

# Добавить callback для поиска чатов из меню
@router.callback_query(F.data == "admin:search_chats")
async def search_chats_callback(callback: types.CallbackQuery, state: FSMContext):
    """Поиск чатов из меню"""
    text = (
        "🔍 Поиск чатов\n\n"
        "Отправьте текст для поиска чатов:\n"
        "• Можно искать по названию чата\n"
        "• Или по ID чата (например: -1001234567890)\n\n"
        "❌ Отмена: отправьте 'отмена'"
    )
    
    await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    await state.set_state(AdminStates.waiting_for_chat_search)
    await callback.answer()


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def format_days_left(days_left: int) -> str:
    """Форматирование дней до сброса (исправлено для HTML)"""
    if days_left == 0:
        return "0 🔚"
    elif days_left < 3:
        return f"{days_left} 🔴"
    elif days_left < 7:
        return f"{days_left} 🟡"
    else:
        return f"{days_left} 🟢"

def safe_format_count(count: int, limit: int) -> str:
    """Форматирование счетчика сообщений с цветами"""
    if limit is None:  # <-- ДОБАВЬТЕ ЭТУ ПРОВЕРКУ!
        return f"{count}/∞"
    
    if count >= limit:
        return f"<b>{count}/{limit} 🔴</b>"
    elif count >= limit * 0.8:
        return f"<b>{count}/{limit} 🟡</b>"
    elif count == 0:
        return f"{count}/{limit} ⚪"
    else:
        return f"{count}/{limit}"

def format_user_display_name(user_data) -> str:
    """Форматирование имени пользователя с иконками"""
    display_name = user_data.first_name or user_data.username or f"User {user_data.id}"
    
    if user_data.username:
        display_name = f"@{user_data.username}"
    elif user_data.first_name:
        display_name = user_data.first_name
    
    return display_name[:20]

async def main_menu_handler(message: types.Message):
    """Отправляет главное меню"""
    from ..utils.admin_check import is_admin
    from ..keyboards.admin import get_main_menu_keyboard
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        from .callbacks import show_user_limits_message
        await show_user_limits_message(message)
        return
    
    text = "👋 Добро пожаловать в панель управления!\n\nВыберите действие:"
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@router.message(StateFilter(AdminStates.waiting_for_notification_text))
async def process_notification_text(message: types.Message, state: FSMContext):
    """Обработка нового текста уведомления"""
    if message.text.startswith('/'):
        return
    
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if new_text.lower() == 'отмена':
        await message.answer("❌ Редактирование отменено")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    try:
        data = await state.get_data()
        notify_type = data.get("notify_type")
        is_global = data.get("is_global", False)
        db_key = data.get("db_key")  # Новое: получаем ключ из данных
        
        # Если db_key не передан, используем старую логику
        if not db_key:
            types_map = {
                "empty": "empty_message",
                "warning": "warning_3_messages", 
                "limit": "limit_exceeded",
                "blocked": "user_blocked",
                "empty_blocked": "empty_message_blocked",  # Новое
                "swear_blocked": "swear_word_blocked"      # Новое
            }
            
            if notify_type not in types_map:
                await message.answer("❌ Неизвестный тип уведомления")
                await state.clear()
                return
            
            db_key = types_map[notify_type]
        
        if is_global:
            # Сохраняем в глобальных настройках
            settings = await db.get_global_settings()
            if settings:
                if not settings.default_notifications:
                    settings.default_notifications = {}
                
                new_notifications = settings.default_notifications.copy()
                new_notifications[db_key] = new_text
                
                success = await db.update_global_notifications(new_notifications)
                
                if success:
                    await message.answer(f"✅ Глобальное уведомление '{notify_type}' обновлено!")
                else:
                    await message.answer("❌ Ошибка сохранения")
            else:
                await message.answer("❌ Настройки не найдены")
        else:
            # Сохраняем для конкретного чата
            chat_id = data.get("chat_id")
            if not chat_id:
                await message.answer("❌ Ошибка: ID чата не найден")
                await state.clear()
                return
            
            chat = await db.get_chat_by_id(chat_id)
            if not chat:
                await message.answer("❌ Чат не найден")
                await state.clear()
                return
            
            if not chat.custom_notifications:
                chat.custom_notifications = {}
            
            new_notifications = chat.custom_notifications.copy()
            new_notifications[db_key] = new_text
            
            success = await db.update_chat_notifications(chat_id, new_notifications)
            
            if success:
                await message.answer(f"✅ Уведомление для чата обновлено!")
            else:
                await message.answer("❌ Ошибка сохранения")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)
    
async def safe_edit_message(callback: types.CallbackQuery, text: str, 
                           keyboard = None, parse_mode: str = None):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        if keyboard:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        else:
            await callback.message.edit_text(text, parse_mode=parse_mode)
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            print(f"❌ Ошибка редактирования сообщения: {e}")
            await callback.answer("❌ Ошибка обновления сообщения")

async def get_exceptions_for_display(chat_id: int = None):
    """Получить исключения для отображения"""
    if chat_id:
        exceptions = await db.get_chat_exceptions(chat_id)
    else:
        settings = await db.get_global_settings()
        if settings and settings.default_exclude_words:
            exceptions = settings.default_exclude_words
        else:
            exceptions = config.DEFAULT_EXCLUDE_WORDS
    
    return exceptions

async def show_user_limits_message(message: types.Message):
    """Показывает лимиты пользователя (для обычных пользователей)"""
    user_id = message.from_user.id
    
    try:
        # Получаем все чаты где есть пользователь
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import UserChatData, Chat
            
            result = await session.execute(
                select(UserChatData, Chat)
                .join(Chat, UserChatData.chat_id == Chat.id)
                .where(UserChatData.user_id == user_id)
                .where(Chat.is_active == True)
            )
            user_chats = result.all()
        
        if user_chats:
            chat_info = ""
            for i, (user_chat_data, chat) in enumerate(user_chats, 1):
                # Получаем лимит пользователя в этом чате
                user_limit = await db.get_user_limit(user_id, chat.id)
                
                # Оставшиеся сообщения
                remaining = max(0, user_limit - user_chat_data.message_count)
                
                status = "🔴 Заблокирован" if user_chat_data.is_muted else f"🟢 Осталось: {remaining}"
                
                chat_info += (
                    f"{i}. {chat.title}\n"
                    f"   📊 Использовано: {user_chat_data.message_count}/{user_limit}\n"
                    f"   🚫 Статус: {status}\n\n"
                )
            
            text = (
                f"👤 Ваши лимиты сообщений\n\n"
                f"Всего активных чатов: {len(user_chats)}\n\n"
                f"{chat_info}\n"
                f"📝 Для увеличения лимита обратитесь к администратору чата"
            )
        else:
            text = (
                "👤 Информация о лимитах\n\n"
                "😕 Вы не состоите ни в одном чате с ботом\n\n"
                "📝 Присоединитесь к чату где работает бот, "
                "чтобы увидеть свои лимиты"
            )
        
        # Кнопка только для обновления
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="user:refresh"
            )
        )
        
        await message.answer(text, reply_markup=builder.as_markup())
        
    except Exception as e:
        print(f"❌ Ошибка показа лимитов пользователя: {e}")
        await message.answer(
            "❌ Ошибка загрузки информации\n\n"
            "Попробуйте позже или обратитесь к администратору"
        )

async def show_user_limits_callback(callback: types.CallbackQuery):
    """Показывает лимиты пользователя в callback (для обычных пользователей)"""
    user_id = callback.from_user.id
    
    try:
        # Получаем все чаты где есть пользователь
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import UserChatData, Chat
            
            result = await session.execute(
                select(UserChatData, Chat)
                .join(Chat, UserChatData.chat_id == Chat.id)
                .where(UserChatData.user_id == user_id)
                .where(Chat.is_active == True)
            )
            user_chats = result.all()
        
        if user_chats:
            chat_info = ""
            for i, (user_chat_data, chat) in enumerate(user_chats, 1):
                # Получаем лимит пользователя в этом чате
                user_limit = await db.get_user_limit(user_id, chat.id)
                
                # Получаем данные с расчетом дней
                user_data = await db.get_user_data_with_days(user_id, chat.id)
                
                if user_data:
                    days_left = user_data['days_left']
                    is_custom = user_data['is_custom']
                else:
                    days_left = 0
                    is_custom = False
                
                # Оставшиеся сообщения
                remaining = max(0, user_limit - user_chat_data.message_count)
                
                # Форматирование с цветами (без HTML в days_display)
                days_display = format_days_left(days_left)
                count_display = safe_format_count(user_chat_data.message_count, user_limit)
                
                # Иконка ручного лимита
                custom_icon = " ⭐" if is_custom else ""
                
                status = "🔴 Заблокирован" if user_chat_data.is_muted else f"🟢 Осталось: {remaining}"
                
                chat_info += (
                    f"{i}. {chat.title}{custom_icon}\n"
                    f"   📊 Использовано: {count_display}\n"
                    f"   📅 Дней до сброса: {days_display}\n"
                    f"   🚫 Статус: {status}\n\n"
                )
            
            text = (
                f"👤 <b>Ваши лимиты сообщений</b>\n\n"
                f"📊 Всего активных чатов: {len(user_chats)}\n\n"
                f"{chat_info}\n"
                f"📝 Для увеличения лимита обратитесь к администратору чата"
            )
        else:
            text = (
                "👤 <b>Информация о лимитах</b>\n\n"
                "😕 Вы не состоите ни в одном чате с ботом"
            )
        
        # Кнопка только для обновления
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="user:refresh"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        print(f"❌ Ошибка показа лимитов пользователя: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки информации\n\n"
            "Попробуйте позже или обратитесь к администратору"
        )

# ===== ПРОВЕРКА АДМИНА ДЛЯ СООБЩЕНИЙ =====

async def check_admin_state(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором для обработки стейтов"""
    return is_admin(user_id)

# ===== ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ =====

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    
    user_id = callback.from_user.id
    from ..utils.admin_check import is_admin
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        # Показываем обычному пользователю только его лимиты
        await show_user_limits_callback(callback)
        await callback.answer()
        return
    
    # Админам показываем полное меню
    text = (
        "👋 Добро пожаловать в панель управления Message Limiter Bot!\n\n"
        "🤖 Что делает этот бот:\n"
        "• Автоматически считает сообщения пользователей\n"
        "• Ограничивает 5 сообщениями в месяц (по умолчанию)\n"
        "• Удаляет 'пустые' сообщения (картинки без текста)\n"
        "• Блокирует при превышении лимита\n"
        "• Автоматически разблокирует 1-го числа\n\n"
        "📊 Управление:\n"
        "Используйте кнопки ниже для настройки:"
    )
    from ..keyboards.admin import get_main_menu_keyboard
    await safe_edit_message(callback, text, get_main_menu_keyboard())
    await callback.answer()

# ===== ОБРАБОТЧИК ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ =====

@router.callback_query(F.data == "user:refresh")
async def user_refresh_callback(callback: types.CallbackQuery):
    """Обновление лимитов для обычных пользователей"""
    user_id = callback.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if is_admin(user_id):
        await callback.answer("❌ Эта функция только для обычных пользователей")
        return
    
    try:
        # Получаем все чаты где есть пользователь
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import UserChatData, Chat
            
            result = await session.execute(
                select(UserChatData, Chat)
                .join(Chat, UserChatData.chat_id == Chat.id)
                .where(UserChatData.user_id == user_id)
                .where(Chat.is_active == True)
            )
            user_chats = result.all()
        
        if user_chats:
            chat_info = ""
            for i, (user_chat_data, chat) in enumerate(user_chats, 1):
                # Получаем лимит пользователя в этом чате
                user_limit = await db.get_user_limit(user_id, chat.id)
                
                # Оставшиеся сообщения
                remaining = max(0, user_limit - user_chat_data.message_count)
                
                status = "🔴 Заблокирован" if user_chat_data.is_muted else f"🟢 Осталось: {remaining}"
                
                chat_info += (
                    f"{i}. {chat.title}\n"
                    f"   📊 Использовано: {user_chat_data.message_count}/{user_limit}\n"
                    f"   🚫 Статус: {status}\n\n"
                )
            
            text = (
                f"👤 Ваши лимиты сообщений\n\n"
                f"Всего активных чатов: {len(user_chats)}\n\n"
                f"{chat_info}\n"
                f"📝 Для увеличения лимита обратитесь к администратору чата"
            )
        else:
            text = (
                "👤 Информация о лимитах\n\n"
                "😕 Вы не состоите ни в одном чате с ботом"
            )
        
        # Кнопка только для обновления
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="user:refresh"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer("✅ Обновлено")
        
    except Exception as e:
        print(f"❌ Ошибка обновления лимитов пользователя: {e}")
        await callback.answer("❌ Ошибка обновления")

# ===== ЗАЩИЩЕННЫЕ ОБРАБОТЧИКИ ДЛЯ АДМИНОВ =====

@router.callback_query(F.data == "admin:global_limits")
async def global_limits_callback(callback: types.CallbackQuery, state: FSMContext):
    """Управление лимитами для всех чатов"""
    try:
        settings = await db.get_global_settings()
        default_limit = settings.default_message_limit if settings else config.DEFAULT_MESSAGE_LIMIT
        
        text = (
            f"📊 Управление глобальными лимитами\n\n"
            f"Текущий лимит по умолчанию: {default_limit} сообщений/месяц\n\n"
            f"Что это значит:\n"
            f"• Этот лимит применяется ко всем новым чатам\n"
            f"• Для существующих чатов можно задать индивидуальный лимит\n"
            f"• Лимит сбрасывается 1-го числа каждого месяца\n\n"
            f"✏️ Изменить лимит:\n"
            f"Отправьте число от 1 до 100\n"
            f"Или нажмите 'Назад'"
        )
        
    except Exception as e:
        text = (
            f"📊 Управление глобальных лимитов\n\n"
            f"Текущий лимит по умолчанию: 5 сообщений/месяц\n\n"
            f"⚠️ Ошибка загрузки\n\n"
            f"✏️ Изменить лимит:\n"
            f"Отправьте число от 1 до 100"
        )
    
    await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    await state.set_state(AdminStates.waiting_for_global_limit)
    await callback.answer()

@router.callback_query(F.data == "admin:chat_list")
async def chat_list_callback(callback: types.CallbackQuery):
    """Список чатов"""
    try:
        chats = await db.get_all_chats()
        
        if chats:
            chat_list = ""
            chat_buttons = []
            
            for i, chat in enumerate(chats, 1):
                if chat.id < -1000000000000:
                    icon = "📢"
                    chat_type = "Канал"
                elif chat.id < -100:
                    icon = "👥"
                    chat_type = "Супергруппа"
                else:
                    icon = "💬"
                    chat_type = "Группа"
                
                display_title = chat.title or f"{chat_type} {abs(chat.id) % 10000}"
                status = "🟢" if chat.is_active else "🔴"
                
                chat_list += f"{i}. {icon} {display_title} {status}\n"
                chat_list += f"   ID: {chat.id} • Лимит: {chat.message_limit}\n\n"
                
                chat_buttons.append({
                    "id": chat.id,
                    "title": display_title,
                    "icon": icon
                })
            
            text = (
                f"📋 Список чатов\n\n"
                f"Всего групп: {len(chats)}\n\n"
                f"{chat_list}\n"
                f"Выберите чат для управления:"
            )
            
            keyboard = get_chats_list_keyboard(chat_buttons)
            
        else:
            text = (
                "📋 Список чатов\n\n"
                "😕 Чатов не найдено\n\n"
                "Как добавить чат:\n"
                "1. Добавьте бота в группу/супергруппу\n"
                "2. Сделайте администратором\n"
                "3. Дайте права удаления и блокировки"
            )
            keyboard = get_back_to_menu_keyboard()
                
    except Exception as e:
        text = (
            "📋 Список чатов\n\n"
            "⚠️ Ошибка загрузки\n\n"
            "Попробуйте позже."
        )
        keyboard = get_back_to_menu_keyboard()
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("chat_select:"))
async def chat_select_callback(callback: types.CallbackQuery):
    """Обработка выбора конкретного чата"""
    try:
        chat_id = int(callback.data.split(":")[1])
        try:
            bot_member = await callback.bot.get_chat_member(chat_id, callback.bot.id)
            bot_in_chat = bot_member.status not in ["kicked", "left"]
        except Exception as e:
            bot_in_chat = False
        chat = await db.get_chat_by_id(chat_id)
        
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        bot_status = "🟢 В чате" if bot_in_chat else "🔴 Удален"
        chat_status = "🟢 Активен" if chat.is_active else "🔴 Неактивен"
        
        text = (
            f"💬 Управление чатом\n\n"
            f"📝 {chat.title}\n\n"
            f"🆔 ID: {chat.id}\n"
            f"📊 Лимит: {chat.message_limit} сообщ./мес.\n"
            f"🟢 Статус: {'Активен' if chat.is_active else 'Неактивен'}\n\n"
            f"Доступные действия:"
        )
        
        keyboard = get_chat_management_keyboard(chat_id)
        await safe_edit_message(callback, text, keyboard)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("chat_manage:"))
async def chat_manage_callback(callback: types.CallbackQuery, state: FSMContext):
    """Управление конкретным чатом"""
    try:
        parts = callback.data.split(":")
        action = parts[1]
        chat_id = int(parts[2])
        
        chat = await db.get_chat_by_id(chat_id)
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        if action == "limit":
            text = (
                f"✏️ Изменение лимита для чата\n\n"
                f"Чат: {chat.title}\n"
                f"Текущий лимит: {chat.message_limit} сообщ./мес.\n\n"
                f"Введите новый лимит (от 1 до 100):"
            )
            
            await safe_edit_message(callback, text, get_back_to_menu_keyboard())
            await state.update_data(chat_id=chat_id)
            await state.set_state(AdminStates.waiting_for_chat_limit)
            
        elif action == "users":
            await show_chat_users(callback, chat_id, chat.title)
            
        elif action == "exceptions":
            await show_chat_exceptions(callback, chat_id, chat.title)
            
        elif action == "notifications":
            await show_chat_notifications(callback, chat_id, chat.title)
            
        elif action == "toggle":
            success = await toggle_chat_status(chat_id, chat.is_active)
            if success:
                status = "деактивирован" if chat.is_active else "активирован"
                await callback.answer(f"✅ Бот {status} в этом чате")
                await chat_select_callback(callback)
            else:
                await callback.answer("❌ Ошибка изменения статуса")
            
        elif action == "back":
            await chat_list_callback(callback)
            
    except Exception as e:
        print(f"❌ Ошибка управления чатом: {e}")
        await callback.answer("❌ Ошибка")
    finally:
        await callback.answer()

async def toggle_chat_status(chat_id: int, current_status: bool) -> bool:
    """Переключить статус чата (активен/неактивен)"""
    try:
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import Chat
            
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
            
            if chat:
                chat.is_active = not current_status
                await session.commit()
                return True
        return False
    except Exception as e:
        print(f"❌ Ошибка изменения статуса чата: {e}")
        return False

async def show_chat_users(callback: types.CallbackQuery, chat_id: int, chat_title: str):
    """Показать пользователей чата с возможностью поиска"""
    try:
        # Сначала проверяем, есть ли бот в этом чате
        try:
            bot_member = await callback.bot.get_chat_member(chat_id, callback.bot.id)
            if bot_member.status in ["kicked", "left"]:
                # Бота нет в чате, показываем сообщение
                text = (
                    f"👥 <b>Пользователи чата '{chat_title}'</b>\n\n"
                    f"🚫 <b>Бот удален из этого чата!</b>\n\n"
                    f"Чтобы управлять пользователями, сначала:\n"
                    f"1. Верните бота в чат\n"
                    f"2. Дайте права администратора\n"
                    f"3. Используйте команду /активировать\n\n"
                    f"<i>Данные сохранены в базе, но недоступны</i>"
                )
                
                from ..keyboards.admin import get_back_to_menu_keyboard
                keyboard = get_back_to_menu_keyboard()
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                await callback.answer("⚠️ Бота нет в этом чате")
                return
        except Exception as e:
            if "kicked" in str(e).lower() or "forbidden" in str(e).lower():
                text = (
                    f"👥 <b>Пользователи чата '{chat_title}'</b>\n\n"
                    f"🚫 <b>Бот удален из этого чата!</b>\n\n"
                    f"Чтобы управлять пользователями, сначала верните бота в чат."
                )
                
                from ..keyboards.admin import get_back_to_menu_keyboard
                keyboard = get_back_to_menu_keyboard()
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                await callback.answer("⚠️ Бота нет в этом чате")
                return
        
        # Добавляем кнопку поиска в интерфейс
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        text = (
            f"👥 <b>Пользователи чата '{chat_title}'</b>\n\n"
            f"📊 <b>Быстрый доступ:</b>\n"
            f"• * - показать всех пользователей\n"
            f"• ID - поиск по ID пользователя\n"
            f"• Имя - поиск по имени\n\n"
            f"<i>Введите текст для поиска или нажмите кнопку:</i>"
        )
        
        builder = InlineKeyboardBuilder()
        
        # Кнопка показа всех пользователей (*)
        builder.row(
            types.InlineKeyboardButton(
                text="⭐ Показать всех пользователей (*)",
                callback_data=f"show_all_users:{chat_id}"
            )
        )
        
        # Кнопка поиска по ID
        builder.row(
            types.InlineKeyboardButton(
                text="🔍 Поиск по ID",
                callback_data=f"search_user_by_id:{chat_id}"
            )
        )
        
        # Кнопка поиска по имени
        builder.row(
            types.InlineKeyboardButton(
                text="👤 Поиск по имени",
                callback_data=f"search_user_by_name:{chat_id}"
            )
        )
        
        # Стандартные кнопки
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад к чату",
                callback_data=f"chat_select:{chat_id}"
            ),
            types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            ),
            width=2
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await callback.message.edit_text(text, parse_mode="HTML")
    finally:
        await callback.answer()

# Добавить обработчики поиска пользователей (после функции show_chat_users)

@router.callback_query(F.data.startswith("show_all_users:"))
async def show_all_users_callback(callback: types.CallbackQuery):
    """Показать всех пользователей в чате (по звездочке *)"""
    try:
        chat_id = int(callback.data.split(":")[1])
        
        # Получаем всех пользователей
        users_data = await db.search_users_in_chat(chat_id, "*")
        
        if users_data:
            users_list = ""
            user_buttons = []
            
            for i, (user_chat_data, user) in enumerate(users_data[:30], 1):
                # Получаем данные с расчетом дней
                user_full_data = await db.get_user_data_with_days(user.id, chat_id)
                
                if user_full_data:
                    days_left = user_full_data['days_left']
                    is_custom = user_full_data['is_custom']
                    user_limit = user_full_data['user_limit']
                else:
                    days_left = 0
                    is_custom = False
                    user_limit = await db.get_user_limit(user.id, chat_id)
                
                # Форматирование
                username = f"@{user.username}" if user.username else f"ID:{user.id}"
                display_name = user.first_name or user.username or f"User {user.id}"
                
                if len(display_name) > 15:
                    display_name = display_name[:13] + ".."
                
                # Иконки статуса
                status_icon = "🔴" if user_chat_data.is_muted else "🟢"
                custom_icon = " ⭐" if is_custom else ""
                
                # Цветовое форматирование счетчика
                count_display = safe_format_count(user_chat_data.message_count, user_limit)
                
                # Дни до сброса
                days_display = format_days_left(days_left)
                
                users_list += (
                    f"{i}. {status_icon}{custom_icon} {display_name}\n"
                    f"   📊 {count_display} • 📅 {days_display}\n"
                    f"   👤 {username}\n\n"
                )
                
                user_buttons.append({
                    'user_chat_data': user_chat_data,
                    'user': user,
                    'display_name': display_name,
                    'is_custom': is_custom
                })
            
            text = (
                f"⭐ <b>Все пользователи чата</b>\n\n"
                f"📊 Всего пользователей: {len(users_data)}\n"
                f"⭐ - ручной лимит\n"
                f"📅 - дни до сброса\n\n"
                f"{users_list}"
                f"<i>Нажмите на номер пользователя для управления:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for i, user_data in enumerate(user_buttons[:10], 1):
                btn_text = f"{i}. {user_data['display_name'][:12]}"
                if len(user_data['display_name']) > 12:
                    btn_text = btn_text[:10] + ".."
                
                if user_data['is_custom']:
                    btn_text += " ⭐"
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"user_select:{user_data['user'].id}:{chat_id}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад к поиску",
                    callback_data=f"chat_manage:users:{chat_id}"
                ),
                types.InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="main_menu"
                ),
                width=2
            )
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        else:
            text = (
                f"⭐ <b>Все пользователи чата</b>\n\n"
                "😕 Пользователей не найдено\n\n"
                "Пользователи появятся здесь после отправки первого сообщения."
            )
            
            from ..keyboards.admin import get_back_to_menu_keyboard
            keyboard = get_back_to_menu_keyboard()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("search_user_by_"))
async def search_user_callback(callback: types.CallbackQuery, state: FSMContext):
    """Поиск пользователя по различным критериям"""
    try:
        parts = callback.data.split(":")
        search_type = parts[0].replace("search_user_by_", "")
        chat_id = int(parts[1])
        
        chat = await db.get_chat_by_id(chat_id)
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        if search_type == "id":
            text = (
                f"🔍 Поиск пользователя по ID\n\n"
                f"💬 Чат: {chat.title}\n\n"
                "Отправьте ID пользователя:\n"
                "❌ Отмена: отправьте 'отмена'"
            )
        elif search_type == "name":
            text = (
                f"🔍 Поиск пользователя по имени\n\n"
                f"💬 Чат: {chat.title}\n\n"
                "Отправьте имя, фамилию или username:\n"
                "(поиск работает по частичному совпадению)\n\n"
                "❌ Отмена: отправьте 'отмена'"
            )
        else:
            await callback.answer("❌ Неизвестный тип поиска")
            return
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
        await state.update_data(chat_id=chat_id, search_type=search_type)
        await state.set_state(AdminStates.waiting_for_user_search)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("user_select:"))
async def user_select_callback(callback: types.CallbackQuery):
    """Обработка выбора конкретного пользователя (с возможностью управления)"""
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        chat_id = int(parts[2])
        
        # Получаем полные данные пользователя с расчетом дней
        user_data = await db.get_user_data_with_days(user_id, chat_id)
        
        if not user_data:
            await callback.answer("❌ Пользователь не найден")
            return
        
        user_chat_data = user_data['user_chat_data']
        user_limit = user_data['user_limit']
        days_left = user_data['days_left']
        is_custom = user_data['is_custom']
        
        # Получаем информацию о пользователе и чате
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import User, Chat
            
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
        
        if not user or not chat:
            await callback.answer("❌ Данные не найдены")
            return
        
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        display_name = user.first_name or user.username or f"User {user.id}"
        
        # Форматирование с цветами
        days_display = format_days_left(days_left)
        count_display = safe_format_count(user_chat_data.message_count, user_limit)
        
        # Проверяем временный лимит
        limit_info = ""
        if user_chat_data.custom_limit:
            if user_chat_data.custom_limit_expires_at:
                expires_at = user_chat_data.custom_limit_expires_at
                days_left_custom = (expires_at - datetime.utcnow()).days
                if days_left_custom > 0:
                    limit_info = f"{user_chat_data.custom_limit} ⏳ ({days_left_custom} дней осталось)"
                else:
                    limit_info = f"{chat.message_limit} (временный лимит истек)"
            else:
                limit_info = f"{user_chat_data.custom_limit} ⭐ (постоянный)"
        else:
            limit_info = f"{chat.message_limit} (чата)"
        
        # Иконка блокировки
        status_icon = "🔴" if user_chat_data.is_muted else "🟢"
        status_text = "Заблокирован" if user_chat_data.is_muted else "Активен"
        
        text = (
            f"👤 <b>Управление пользователем</b>\n\n"
            f"📝 {display_name}\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Username: {username}\n"
            f"💬 Чат: {chat.title if chat else 'Неизвестно'}\n"
            f"📊 Сообщений: {count_display}\n"
            f"🎯 Лимит: {limit_info}\n"
            f"📅 Дней до сброса: {days_display}\n"
            f"🚫 Статус: {status_icon} {status_text}\n\n"
            f"<i>✏️ Формат изменения лимита:</i>\n"
            f"• <code>60</code> - постоянный лимит\n"
            f"• <code>60/30</code> - 60 сообщений на 30 дней\n"
            f"• <code>0</code> - сбросить к лимиту чата\n\n"
            f"<i>Доступные действия:</i>"
        )
        
        from ..keyboards.admin import get_user_management_keyboard
        keyboard = get_user_management_keyboard(user_id, chat_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("user_limit:"))
async def user_limit_callback(callback: types.CallbackQuery, state: FSMContext):
    """Изменение лимита для конкретного пользователя"""
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        chat_id = int(parts[2])
        
        current_limit = await db.get_user_limit(user_id, chat_id)
        
        text = (
            f"✏️ Изменение лимита для пользователя\n\n"
            f"Пользователь ID: {user_id}\n"
            f"Чат ID: {chat_id}\n"
            f"Текущий лимит: {current_limit} сообщ./мес.\n\n"
            f"Формат ввода:\n"
            f"• 60 - постоянный лимит\n"
            f"• 60/30 - 60 сообщений на 30 дней\n"
            f"• 0</ - сбросить к лимиту чата\n\n"
            f"Отправьте новый лимит:"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
        await state.update_data(user_id=user_id, chat_id=chat_id)
        await state.set_state(AdminStates.waiting_for_user_limit)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("user_reset_limit:"))
async def user_reset_limit_callback(callback: types.CallbackQuery):
    """Сброс индивидуального лимита пользователя"""
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        chat_id = int(parts[2])
        
        success = await db.update_user_limit(user_id, chat_id, None)
        if success:
            await callback.answer("✅ Лимит пользователя сброшен к лимиту чата")
            await user_select_callback(callback)
        else:
            await callback.answer("❌ Ошибка сброса лимита")
            
    except Exception as e:
        await callback.answer("❌ Ошибка")
    finally:
        await callback.answer()

# В функции exceptions_callback:

@router.callback_query(F.data == "admin:exceptions")
async def exceptions_callback(callback: types.CallbackQuery):
    """Управление исключениями (перенаправление в новый модуль)"""
    try:
        # Прямой вызов функции управления исключениями
        from .exceptions import manage_exceptions_callback
        await manage_exceptions_callback(callback)
        
    except Exception as e:
        text = f"❌ Ошибка загрузки исключений\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

# Старые функции исключений оставлены для обратной совместимости
async def show_chat_exceptions(callback: types.CallbackQuery, chat_id: int, chat_title: str):
    """Показать исключения для конкретного чата"""
    try:
        exceptions = await db.get_chat_exceptions(chat_id)
        
        exceptions_text = "\n".join([f"• {word}" for word in exceptions[:15]])
        
        text = (
            f"🔧 Исключения для чата '{chat_title}'\n\n"
            f"📋 Текущие исключения ({len(exceptions)}):\n"
            f"{exceptions_text}\n\n"
            f"Управление:\n"
            f"Настройки исключений доступны в главном меню"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()
@router.callback_query(F.data == "admin:notification_settings")
async def notification_settings_callback(callback: types.CallbackQuery):
    """Настройки уведомлений (текущая версия - в разработке)"""
    try:
        text = (
            "⚙️ <b>Настройки уведомлений</b>\n\n"
            "🔧 <b>Эта функция находится в разработке</b>\n\n"
            "Ожидайте в следующих обновлениях!"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
        await callback.answer("⏳ В разработке")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка")

'''@router.callback_query(F.data == "admin:notification_settings")
async def notification_settings_callback(callback: types.CallbackQuery):
    """Настройки уведомлений"""
    try:
        settings = await db.get_global_settings()
        
        if settings and settings.default_notifications:
            notifications = settings.default_notifications
        else:
            notifications = config.DEFAULT_NOTIFICATIONS
        
        text = (
            "⚙️ <b>Настройки уведомлений</b>\n\n"
            
            "📝 <b>Текущие тексты уведомлений:</b>\n\n"
            
            f"1. 🗑️ <b>Пустые сообщения:</b>\n"
            f"{notifications.get('empty_message', 'Нет текста')[:60]}...\n\n"
            
            f"2. ⚠️ <b>Предупреждение (3 сообщение):</b>\n"
            f"{notifications.get('warning_3_messages', 'Нет текста')[:60]}...\n\n"
            
            f"3. 🚫 <b>Лимит исчерпан:</b>\n"
            f"{notifications.get('limit_exceeded', 'Нет текста')[:60]}...\n\n"
            
            f"4. 🔒 <b>Заблокированным пользователям:</b>\n"
            f"{notifications.get('user_blocked', 'Нет текста')[:60]}...\n\n"
            
            "✏️ <b>Редактирование:</b>\n"
            "Выберите уведомление для изменения"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="🗑️ Пустые сообщения",
                callback_data="notify:empty"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⚠️ Предупреждение (3 сообщение)",
                callback_data="notify:warning"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🚫 Лимит исчерпан",
                callback_data="notify:limit"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔒 Заблокированным",
                callback_data="notify:blocked"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🌐 Управление уведомлениями",
                callback_data="notifications:manage"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="main_menu"
            ),
            types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            ),
            width=2
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("notify:"))
async def notify_settings_callback(callback: types.CallbackQuery, state: FSMContext):
    """Настройка конкретного уведомления"""
    notify_type = callback.data.split(":")[1]
    
    types_map = {
        "empty": "пустых сообщений",
        "warning": "предупреждения (3 сообщение)",
        "limit": "лимита исчерпан",
        "blocked": "заблокированным пользователям"
    }
    
    settings = await db.get_global_settings()
    if settings and settings.default_notifications:
        notifications = settings.default_notifications
    else:
        notifications = config.DEFAULT_NOTIFICATIONS
    
    current_text = notifications.get({
        "empty": "empty_message",
        "warning": "warning_3_messages",
        "limit": "limit_exceeded",
        "blocked": "user_blocked"
    }[notify_type], "")
    
    if notify_type in types_map:
        text = (
            f"✏️ <b>Редактирование уведомления</b>\n\n"
            f"📝 <b>Тип:</b> {types_map[notify_type]}\n\n"
            f"<b>Доступные переменные:</b>\n"
            f"• {{N}} - оставшееся количество сообщений\n"
            f"• {{contact_link}} - контакт для покупки\n\n"
            f"<b>Текущий текст:</b>\n"
            f"{current_text}\n\n"
        )
        
        from ..keyboards.admin import get_back_to_menu_keyboard
        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
        
        await state.update_data(notify_type=notify_type, is_global=True)
        await state.set_state(AdminStates.waiting_for_notification_text)
        
    await callback.answer()'''

async def show_chat_notifications(callback: types.CallbackQuery, chat_id: int, chat_title: str):
    """Показать уведомления для конкретного чата"""
    try:
        notifications = await db.get_chat_notifications(chat_id)
        
        text = (
            f"⚙️ <b>Уведомления для чата '{chat_title}'</b>\n\n"
            f"📋 <b>Текущие уведомления:</b>\n\n"
            f"1. 🗑️ <b>Пустые сообщения:</b>\n"
            f"{notifications.get('empty_message', 'По умолчанию')[:50]}...\n\n"
            f"2. ⚠️ <b>Предупреждение:</b>\n"
            f"{notifications.get('warning_3_messages', 'По умолчанию')[:50]}...\n\n"
            f"3. 🚫 <b>Лимит исчерпан:</b>\n"
            f"{notifications.get('limit_exceeded', 'По умолчанию')[:50]}...\n\n"
            f"4. 🔒 <b>Заблокированным:</b>\n"
            f"{notifications.get('user_blocked', 'По умолчанию')[:50]}...\n\n"
            f"<i>Управление уведомлениями доступно в главном меню</i>"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data == "admin:global_settings")
async def global_settings_callback(callback: types.CallbackQuery):
    """Глобальные настройки"""
    try:
        settings = await db.get_global_settings()
        
        contact_link = settings.contact_link if settings else ""
        default_limit = settings.default_message_limit if settings else config.DEFAULT_MESSAGE_LIMIT
        
        # Получаем новые настройки
        min_length = getattr(settings, 'default_min_message_length', 20) if settings else 20
        banned_words_count = len(getattr(settings, 'default_banned_words', [])) if settings else 0
        
        text = (
            "⚙️ <b>Глобальные настройки</b>\n\n"
            
            f"📊 <b>Лимит по умолчанию:</b> {default_limit} сообщ./мес.\n"
            f"📏 <b>Минимальная длина:</b> {min_length} символов\n"
            f"🚫 <b>Запрещенных слов:</b> {banned_words_count}\n\n"
            
            f"🔗 <b>Контактная ссылка:</b>\n"
            f"{contact_link if contact_link else 'Не задана'}\n\n"
            
            "<i>Использование:</i>\n"
            "Контактная ссылка используется в уведомлениях "
            "при достижении лимита сообщений.\n\n"
            
            "<i>Выберите настройку для изменения:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔗 Изменить контактную ссылку",
                callback_data="settings:contact"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="📊 Изменить лимит по умолчанию",
                callback_data="admin:global_limits"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Автосброс лимитов",
                callback_data="settings:auto_reset"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="📏 Настройки длины сообщений",
                callback_data="exceptions:length_settings"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🚫 Запрещенные слова",
                callback_data="exceptions:banned_words"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад в меню",
                callback_data="main_menu"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки настроек\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data == "settings:contact")
async def settings_contact_callback(callback: types.CallbackQuery, state: FSMContext):
    """Изменение контактной ссылки"""
    try:
        settings = await db.get_global_settings()
        current_link = settings.contact_link if settings else ""
        
        text = (
            "🔗 <b>Изменение контактной ссылки</b>\n\n"
            "Эта ссылка используется в уведомлениях при достижении лимита.\n\n"
            "<b>Примеры:</b>\n"
            "• https://t.me/username\n"
            "• @username\n"
            "• https://example.com\n\n"
            f"<b>Текущая ссылка:</b>\n"
            f"{current_link if current_link else 'Не задана'}\n\n"
            "<i>Отправьте новую ссылку или оставьте пустым:</i>"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
        await state.set_state(AdminStates.waiting_for_contact_link)
        
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data == "admin:help")
async def help_callback(callback: types.CallbackQuery):
    """Помощь по админ-панели"""
    text = (
        "❓ <b>Помощь по админ-панели</b>\n\n"
        
        "📊 <b>Разделы управления:</b>\n\n"
        
        "• <b>Управление лимитами</b>\n"
        "Настройка лимитов сообщений для всех чатов\n\n"
        
        "• <b>Список чатов</b>\n"
        "Просмотр и управление всеми чатами с ботом\n\n"
        
        "• <b>Настройки уведомлений</b>\n"
        "Изменение текстов уведомлений\n\n"
        
        "• <b>Исключения и фильтры</b>\n"
        "Управление словами/фразами, которые не учитываются\n"
        "Настройка запрещенных слов и минимальной длины\n\n"
        
        "• <b>Глобальные настройки</b>\n"
        "Настройка контактной ссылки и других параметров\n\n"
        
        "• <b>Статистика</b>\n"
        "Просмотр статистики использования бота\n\n"
        
        "• <b>Безопасность</b>\n"
        "Настройки безопасности и логирования\n\n"
        
        "🔄 <b>Автоматические функции:</b>\n"
        "• Сброс счетчиков 1-го числа\n"
        "• Автоматическая блокировка\n"
        "• Авторазблокировка через 30 дней\n"
        "• Удаление пустых сообщений\n\n"
        
        "📏 <b>Новые функции:</b>\n"
        "• Минимальная длина сообщений (20 символов)\n"
        "• Запрещенные слова (блокировка на 3 дня)\n"
        "• Ограничение пустых сообщений (3 попытки)\n\n"
        
        "📞 <b>Поддержка:</b>\n"
        "Проблемы или вопросы? Сохраните эту информацию!"
    )
    
    await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "test_button")
async def test_button_callback(callback: types.CallbackQuery):
    """Тестовая кнопка"""
    await callback.answer("✅ Тестовая кнопка работает!", show_alert=True)

@router.callback_query(F.data == "admin:statistics")
async def statistics_callback(callback: types.CallbackQuery):
    """Статистика"""
    try:
        text = (
            "📈 <b>Статистика бота</b>\n\n"
            "Выберите раздел статистики:"
        )
        
        await safe_edit_message(callback, text, get_statistics_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("stats:"))
async def stats_callback(callback: types.CallbackQuery):
    """Разделы статистики"""
    stats_type = callback.data.split(":")[1]
    
    try:
        if stats_type == "general":
            stats = await db.get_general_statistics()
            
            text = (
                "📊 <b>Общая статистика бота</b>\n\n"
                f"📈 <b>Показатели:</b>\n"
                f"• Чатов: {stats.get('total_chats', 0)}\n"
                f"• Пользователей: {stats.get('total_users', 0)}\n"
                f"• Сообщений: {stats.get('total_messages', 0)}\n"
                f"• Заблокировано: {stats.get('blocked_users', 0)}\n\n"
                f"🔄 <b>Автоматические функции:</b>\n"
                f"• Автосброс лимитов: ✅ Включен (1-го числа)\n"
                f"• Удаление пустых сообщений: ✅ Включено\n"
                f"• Автоблокировка: ✅ Включена\n"
                f"• Авторазблокировка: ✅ Включена (30 дней)\n\n"
                f"⏰ <b>Последнее обновление:</b> {stats.get('timestamp', 'Неизвестно')}"
            )
            
        elif stats_type == "users":
            async with db.async_session() as session:
                from sqlalchemy import select, func
                from ..models.schemas import UserChatData, User
                
                result = await session.execute(
                    select(UserChatData, User)
                    .join(User, UserChatData.user_id == User.id)
                    .order_by(UserChatData.message_count.desc())
                    .limit(10)
                )
                top_users = result.all()
                
                if top_users:
                    users_list = ""
                    for i, (user_chat_data, user) in enumerate(top_users, 1):
                        username = f"@{user.username}" if user.username else f"ID:{user.id}"
                        display_name = user.first_name or user.username or f"User {user.id}"
                        
                        users_list += (
                            f"{i}. {display_name[:15]}\n"
                            f"   📊 {user_chat_data.message_count} сообщ. • {username}\n\n"
                        )
                    
                    text = (
                        "👥 <b>Топ пользователей по сообщениям</b>\n\n"
                        f"{users_list}"
                        f"<i>Показаны топ-10 пользователей</i>"
                    )
                else:
                    text = (
                        "👥 <b>Статистика пользователей</b>\n\n"
                        "😕 Нет данных о пользователях"
                    )
            
        elif stats_type == "chats":
            chats = await db.get_all_chats()
            
            if chats:
                chat_stats = ""
                for i, chat in enumerate(chats[:10], 1):
                    status = "🟢" if chat.is_active else "🔴"
                    chat_stats += (
                        f"{i}. {status} {chat.title[:20]}\n"
                        f"   Лимит: {chat.message_limit} • ID: {chat.id}\n\n"
                    )
                
                text = (
                    f"💬 <b>Статистика чатов</b>\n\n"
                    f"Всего чатов: {len(chats)}\n\n"
                    f"{chat_stats}"
                    f"<i>Показаны первые 10 чатов</i>"
                )
            else:
                text = (
                    "💬 <b>Статистика чатов</b>\n\n"
                    "😕 Чатов не найдено"
                )
            
        elif stats_type == "monthly":
            # ЕЖЕМЕСЯЧНАЯ СТАТИСТИКА
            async with db.async_session() as session:
                from sqlalchemy import select, func, extract
                from datetime import datetime, timedelta
                from ..models.schemas import UserChatData, Chat, ActionLog, User
                
                # Текущий месяц и год
                now = datetime.now()
                current_month = now.month
                current_year = now.year
                
                # Сообщения по месяцам (последние 6 месяцев)
                monthly_stats = {}
                for i in range(6):
                    month_date = now - timedelta(days=30*i)
                    month_key = f"{month_date.year}-{month_date.month:02d}"
                    
                    # Считаем сообщения за месяц
                    result = await session.execute(
                        select(func.count(UserChatData.id))
                        .where(
                            extract('year', UserChatData.updated_at) == month_date.year,
                            extract('month', UserChatData.updated_at) == month_date.month
                        )
                    )
                    message_count = result.scalar() or 0
                    
                    # Блокировки за месяц
                    result = await session.execute(
                        select(func.count(ActionLog.id))
                        .where(
                            ActionLog.action_type == "user_blocked",
                            extract('year', ActionLog.created_at) == month_date.year,
                            extract('month', ActionLog.created_at) == month_date.month
                        )
                    )
                    blocks_count = result.scalar() or 0
                    
                    monthly_stats[month_key] = {
                        "messages": message_count,
                        "blocks": blocks_count
                    }
                
                # Формируем текст статистики
                stats_text = ""
                for month, data in sorted(monthly_stats.items(), reverse=True):
                    year, month_num = month.split('-')
                    month_name = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", 
                                 "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"][int(month_num)-1]
                    
                    stats_text += (
                        f"📅 {month_name} {year}:\n"
                        f"   📊 Сообщений: {data['messages']}\n"
                        f"   🔒 Блокировок: {data['blocks']}\n\n"
                    )
                
                # Активность по чатам (топ-5)
                result = await session.execute(
                    select(Chat.title, func.count(UserChatData.id))
                    .join(UserChatData, Chat.id == UserChatData.chat_id)
                    .group_by(Chat.id)
                    .order_by(func.count(UserChatData.id).desc())
                    .limit(5)
                )
                top_chats = result.all()
                
                chats_text = ""
                if top_chats:
                    for i, (chat_title, msg_count) in enumerate(top_chats, 1):
                        chats_text += f"{i}. {chat_title[:20]}: {msg_count} сообщ.\n"
                
                # Самые активные пользователи (топ-5)
                result = await session.execute(
                    select(UserChatData.user_id, User.first_name, User.username, func.count(UserChatData.id))
                    .join(User, UserChatData.user_id == User.id)
                    .group_by(UserChatData.user_id, User.first_name, User.username)
                    .order_by(func.count(UserChatData.id).desc())
                    .limit(5)
                )
                top_users = result.all()
                
                users_text = ""
                if top_users:
                    for i, (user_id, first_name, username, msg_count) in enumerate(top_users, 1):
                        display_name = first_name or username or f"User {user_id}"
                        users_text += f"{i}. {display_name[:15]}: {msg_count} сообщ.\n"
                
                text = (
                    "📅 <b>Ежемесячная статистика</b>\n\n"
                    
                    "<b>📈 Динамика активности (последние 6 месяцев):</b>\n"
                    f"{stats_text}\n"
                    
                    "<b>🏆 Топ-5 самых активных чатов:</b>\n"
                    f"{chats_text if chats_text else 'Нет данных'}\n\n"
                    
                    "<b>👥 Топ-5 самых активных пользователей:</b>\n"
                    f"{users_text if users_text else 'Нет данных'}\n\n"
                    
                    "<b>📊 Общая статистика за текущий месяц:</b>\n"
                    f"• Сообщений: {monthly_stats.get(f'{current_year}-{current_month:02d}', {}).get('messages', 0)}\n"
                    f"• Блокировок: {monthly_stats.get(f'{current_year}-{current_month:02d}', {}).get('blocks', 0)}\n\n"
                    
                    "<i>📤 Экспорт данных в разработке...</i>"
                )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки статистики\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data == "admin:security")
async def security_callback(callback: types.CallbackQuery):
    """Безопасность"""
    text = (
        "🛡️ <b>Настройки безопасности</b>\n\n"
        "Выберите раздел:"
    )
    
    await safe_edit_message(callback, text, get_security_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("security:"))
async def security_section_callback(callback: types.CallbackQuery):
    """Разделы безопасности"""
    section = callback.data.split(":")[1]
    
    try:
        if section == "settings":
            settings = await db.get_global_settings()
            auto_unblock_days = settings.auto_unblock_days if settings else 30
            log_enabled = settings.security_log_enabled if settings else True
            
            text = (
                "🛡️ <b>Настройки безопасности</b>\n\n"
                "<b>🔒 Текущие настройки:</b>\n"
                f"• Логирование действий: {'✅ Включено' if log_enabled else '❌ Выключено'}\n"
                f"• Авторазблокировка: ✅ Включена ({auto_unblock_days} дней)\n"
                f"• Проверка администраторов: ✅ Включена\n"
                f"• Защита от спама: ✅ Включена\n"
                f"• Резервное копирование: ✅ Включено (еженедельно)\n\n"
                "<b>⚙️ Рекомендации по безопасности:</b>\n"
                "1. Регулярно проверяйте логи действий\n"
                "2. Настройте доступ только для доверенных администраторов\n"
                "3. Включите двухфакторную аутентификацию в Telegram\n"
                "4. Храните токен бота в безопасности\n"
                "5. Регулярно обновляйте бота"
            )
            
        elif section == "admins":
            text = (
                "👮‍♂️ <b>Управление администраторами</b>\n\n"
                "<b>🔐 Текущие права:</b>\n"
                "• Доступ к админ-панели: Владелец бота\n"
                "• Управление чатами: Владелец бота\n"
                "• Просмотр статистики: Владелец бота\n\n"
                "<b>⚙️ Безопасность:</b>\n"
                "• Токен бота защищен в .env файле\n"
                "• Нет публичного доступа к БД\n"
                "• Все действия логируются\n\n"
                "<b>📋 Лучшие практики:</b>\n"
                "1. Не делитесь доступом с ненадежными лицами\n"
                "2. Регулярно меняйте пароли\n"
                "3. Проверяйте логи подозрительных действий"
            )
            
        elif section == "blocked":
            async with db.async_session() as session:
                from sqlalchemy import select
                from ..models.schemas import UserChatData, User, Chat
                
                result = await session.execute(
                    select(UserChatData, User, Chat)
                    .join(User, UserChatData.user_id == User.id)
                    .join(Chat, UserChatData.chat_id == Chat.id)
                    .where(UserChatData.is_muted == True)
                    .order_by(UserChatData.updated_at.desc())
                )
                blocked_users = result.all()
                
                if blocked_users:
                    blocked_list = ""
                    for i, (user_chat_data, user, chat) in enumerate(blocked_users[:10], 1):
                        username = f"@{user.username}" if user.username else f"ID:{user.id}"
                        display_name = user.first_name or user.username or f"User {user.id}"
                        
                        blocked_list += (
                            f"{i}. 🔴 {display_name[:15]}\n"
                            f"   💬 {chat.title[:20]}\n"
                            f"   📊 {user_chat_data.message_count} сообщ. • {username}\n\n"
                        )
                    
                    text = (
                        f"🚫 <b>Заблокированные пользователи</b>\n\n"
                        f"Всего заблокировано: {len(blocked_users)}\n\n"
                        f"{blocked_list}"
                        f"<i>Показаны последние 10 блокировок</i>\n\n"
                        f"🔄 Авторазблокировка через 30 дней"
                    )
                else:
                    text = (
                        "🚫 <b>Заблокированные пользователи</b>\n\n"
                        "✅ Нет заблокированных пользователей\n\n"
                        "🎉 Все пользователи активны и соблюдают лимиты!"
                    )
            
        elif section == "logs":
            async with db.async_session() as session:
                from sqlalchemy import select
                from ..models.schemas import ActionLog
                
                result = await session.execute(
                    select(ActionLog)
                    .order_by(ActionLog.created_at.desc())
                    .limit(20)
                )
                logs = result.scalars().all()
                
                if logs:
                    log_list = ""
                    for i, log in enumerate(logs, 1):
                        time = log.created_at.strftime("%H:%M")
                        details = log.details or ""
                        if details:
                            details = details[:50]
                        
                        icons = {
                            "message_received": "📨",
                            "user_blocked": "🔒",
                            "warning_sent": "⚠️",
                            "empty_message_deleted": "🗑️",
                            "message_excepted": "📝",
                            "bot_added_to_chat": "🤖",
                            "bot_removed_from_chat": "❌",
                            "monthly_reset": "🔄",
                            "auto_unblock": "🔓"
                        }
                        
                        icon = icons.get(log.action_type, "📋")
                        log_list += f"{i}. {icon} {time} {log.action_type}\n"
                        if details:
                            log_list += f"   {details}\n"
                        log_list += "\n"
                    
                    text = (
                        "📋 <b>Логи действий</b>\n\n"
                        f"Всего записей в логах: {len(logs)}\n\n"
                        f"{log_list}"
                        f"<i>Показаны последние 20 записей</i>"
                    )
                else:
                    text = (
                        "📋 <b>Логи действий</b>\n\n"
                        "📭 Логи пусты\n\n"
                        "Логи появятся после действий в боте."
                    )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        text = f"❌ Ошибка загрузки\n\n{str(e)}"
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("user_unblock:"))
async def user_unblock_callback(callback: types.CallbackQuery):
    """Разблокировка пользователя"""
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        chat_id = int(parts[2])
        
        success = await unblock_user(callback.bot, user_id, chat_id)
        
        if success:
            await callback.answer("✅ Пользователь разблокирован")
            await user_select_callback(callback)
        else:
            await callback.answer("❌ Ошибка разблокировки")
            
    except Exception as e:
        await callback.answer("❌ Ошибка")
    finally:
        await callback.answer()

async def unblock_user(bot, user_id: int, chat_id: int) -> bool:
    """Разблокировать пользователя в чате"""
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=types.ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import UserChatData
            
            result = await session.execute(
                select(UserChatData)
                .where(UserChatData.user_id == user_id)
                .where(UserChatData.chat_id == chat_id)
            )
            user_chat_data = result.scalar_one_or_none()
            
            if user_chat_data:
                user_chat_data.is_muted = False
                user_chat_data.mute_until = None
                user_chat_data.message_count = 0
                await session.commit()
        
        await db.log_action("manual_unblock", user_id=user_id, chat_id=chat_id, 
                          details="Ручная разблокировка администратором")
        
        print(f"✅ Пользователь {user_id} разблокирован в чате {chat_id}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка разблокировки пользователя {user_id}: {e}")
        await db.log_action("unblock_error", user_id=user_id, chat_id=chat_id, 
                          details=f"Ошибка: {str(e)}")
        return False

@router.callback_query(F.data == "settings:auto_reset")
async def auto_reset_callback(callback: types.CallbackQuery):
    """Настройка автосброса лимитов"""
    settings = await db.get_global_settings()
    auto_unblock_days = settings.auto_unblock_days if settings else 30
    
    text = (
        "🔄 <b>Настройка автосброса лимитов</b>\n\n"
        "<b>📅 Текущие настройки:</b>\n"
        "• Автосброс лимитов: ✅ Включен\n"
        "• Дата сброса: 1-е число каждого месяца\n"
        "• Время сброса: 00:01\n"
        f"• Авторазблокировка: ✅ Включена ({auto_unblock_days} дней)\n\n"
        "<b>⚙️ Что происходит при сбросе:</b>\n"
        "1. Счетчики сообщений обнуляются\n"
        "2. Заблокированные пользователи разблокируются\n"
        "3. Сохраняется статистика\n"
        "4. Создается резервная копия БД\n\n"
        "<b>🛡️ Безопасность:</b>\n"
        "• Все действия логируются\n"
        "• Создаются резервные копии\n"
        "• Можно восстановить данные\n\n"
        "<b>📊 Следующий сброс:</b> 1-го числа следующего месяца, 00:01"
    )
    
    await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

# ===== ОБРАБОТКА СООБЩЕНИЙ (СТЕЙТЫ) С ПРОВЕРКОЙ АДМИНА =====

@router.message(StateFilter(AdminStates.waiting_for_global_limit))
async def process_global_limit(message: types.Message, state: FSMContext):
    """Обработка нового глобального лимита"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    try:
        new_limit = int(message.text)
        
        if 1 <= new_limit <= 100:
            success = await db.update_global_settings(default_limit=new_limit)
            if success:
                await message.answer(
                    f"✅ Глобальный лимит изменен на {new_limit} сообщений/месяц"
                )
            else:
                await message.answer("❌ Ошибка сохранения в БД")
        else:
            await message.answer("❌ Лимит должен быть от 1 до 100")
            
    except ValueError:
        await message.answer("❌ Введите число от 1 до 100")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_chat_limit))
async def process_chat_limit(message: types.Message, state: FSMContext):
    """Обработка нового лимита для чата"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    try:
        data = await state.get_data()
        chat_id = data.get("chat_id")
        
        if not chat_id:
            await message.answer("❌ Ошибка: ID чата не найден")
            await state.clear()
            return
        
        new_limit = int(message.text)
        
        if 1 <= new_limit <= 100:
            success = await db.update_chat_limit(chat_id, new_limit)
            if success:
                await message.answer(
                    f"✅ Лимит для чата изменен на {new_limit} сообщений/месяц"
                )
            else:
                await message.answer("❌ Ошибка сохранения в БД")
        else:
            await message.answer("❌ Лимит должен быть от 1 до 100")
            
    except ValueError:
        await message.answer("❌ Введите число от 1 до 100")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_user_limit))
async def process_user_limit(message: types.Message, state: FSMContext):
    """Обработка нового лимита для пользователя с поддержкой временных лимитов"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    try:
        data = await state.get_data()
        user_id = data.get("user_id")
        chat_id = data.get("chat_id")
        
        if not user_id or not chat_id:
            await message.answer("❌ Ошибка: данные не найдены")
            await state.clear()
            return
        
        text = message.text.strip()
        
        # Проверяем формат: "60/60" или просто "60"
        if '/' in text:
            # Формат с днями: "лимит/дни"
            try:
                limit_str, days_str = text.split('/')
                new_limit = int(limit_str.strip())
                days = int(days_str.strip())
                
                if 1 <= new_limit <= 1000 and 1 <= days <= 365:
                    success = await db.set_temporary_user_limit(user_id, chat_id, new_limit, days)
                    if success:
                        expires_at = datetime.utcnow() + timedelta(days=days)
                        
                        # Очищаем кэш счетчика пустых сообщений
                        from ..handlers.group import user_empty_message_counters
                        empty_key = (user_id, chat_id)
                        if empty_key in user_empty_message_counters:
                            del user_empty_message_counters[empty_key]
                        
                        await message.answer(
                            f"✅ Установлен временный лимит:\n"
                            f"• {new_limit} сообщений\n"
                            f"• на {days} дней\n"
                            f"• до {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"📊 <b>Важно:</b> Счетчик сообщений сброшен до 0!\n"
                            f"🗑️ Счетчик пустых сообщений сброшен."
                        )
                        
                        # Логируем действие
                        await db.log_action(
                            "set_temporary_limit",
                            user_id=user_id,
                            chat_id=chat_id,
                            details=f"Лимит: {new_limit} на {days} дней"
                        )
                        
                        # Если пользователь был заблокирован - разблокируем
                        async with db.async_session() as session:
                            from sqlalchemy import select
                            from ..models.schemas import UserChatData
                            
                            result = await session.execute(
                                select(UserChatData)
                                .where(UserChatData.user_id == user_id)
                                .where(UserChatData.chat_id == chat_id)
                            )
                            user_chat_data = result.scalar_one_or_none()
                            
                            if user_chat_data and user_chat_data.is_muted:
                                # Разблокируем пользователя
                                try:
                                    await message.bot.restrict_chat_member(
                                        chat_id=chat_id,
                                        user_id=user_id,
                                        permissions=types.ChatPermissions(
                                            can_send_messages=True,
                                            can_send_media_messages=True,
                                            can_send_polls=True,
                                            can_send_other_messages=True,
                                            can_add_web_page_previews=True,
                                            can_change_info=False,
                                            can_invite_users=True,
                                            can_pin_messages=False
                                        )
                                    )
                                    user_chat_data.is_muted = False
                                    user_chat_data.mute_until = None
                                    await session.commit()
                                    
                                    await message.answer(
                                        f"🔓 Пользователь автоматически разблокирован!\n"
                                        f"Теперь он может отправлять сообщения с новым лимитом."
                                    )
                                    
                                    await db.log_action(
                                        "auto_unblock_with_limit",
                                        user_id=user_id,
                                        chat_id=chat_id,
                                        details=f"Авторазблокировка при установке лимита {new_limit}"
                                    )
                                    
                                except Exception as e:
                                    print(f"⚠️ Не удалось автоматически разблокировать пользователя: {e}")
                        
                    else:
                        await message.answer("❌ Ошибка сохранения временного лимита")
                else:
                    await message.answer("❌ Лимит: 1-1000, дни: 1-365")
                    
            except ValueError:
                await message.answer("❌ Формат: лимит/дни (пример: 60/30)")
                
        elif text == "0":
            # Сброс лимита - ОСОБАЯ ОБРАБОТКА
            try:
                async with db.async_session() as session:
                    from sqlalchemy import select
                    from ..models.schemas import UserChatData
                    
                    result = await session.execute(
                        select(UserChatData)
                        .where(UserChatData.user_id == user_id)
                        .where(UserChatData.chat_id == chat_id)
                    )
                    user_chat_data = result.scalar_one_or_none()
                    
                    if user_chat_data:
                        # Получаем лимит чата для сообщения
                        from sqlalchemy import select
                        from ..models.schemas import Chat
                        
                        chat_result = await session.execute(
                            select(Chat).where(Chat.id == chat_id)
                        )
                        chat = chat_result.scalar_one_or_none()
                        chat_limit = chat.message_limit if chat else 5
                        
                        # Сохраняем текущий счетчик
                        current_count = user_chat_data.message_count
                        
                        # Сбрасываем ВСЁ
                        user_chat_data.custom_limit = None
                        user_chat_data.custom_limit_expires_at = None
                        user_chat_data.is_custom_limit_active = False
                        # НЕ сбрасываем счетчик при сбросе лимита!
                        
                        await session.commit()
                        
                        # Очищаем кэш
                        from ..handlers.group import user_empty_message_counters
                        empty_key = (user_id, chat_id)
                        if empty_key in user_empty_message_counters:
                            del user_empty_message_counters[empty_key]
                        
                        await message.answer(
                            f"✅ Индивидуальный лимит пользователя сброшен.\n\n"
                            f"Теперь используется лимит чата: {chat_limit}\n"
                            f"📊 Счетчик сообщений сохранен: {current_count}\n"
                            f"🗑️ Счетчик пустых сообщений сброшен."
                        )
                        
                        await db.log_action(
                            "reset_user_limit",
                            user_id=user_id,
                            chat_id=chat_id,
                            details=f"Сброшен к лимиту чата {chat_limit}, счетчик: {current_count}"
                        )
                        
                    else:
                        await message.answer("❌ Пользователь не найден")
                        
            except Exception as e:
                await message.answer(f"❌ Ошибка сброса лимита: {str(e)}")
                await db.log_action(
                    "reset_limit_error",
                    user_id=user_id,
                    chat_id=chat_id,
                    details=f"Ошибка: {str(e)}"
                )
                
        else:
            # Просто число - постоянный лимит
            try:
                new_limit = int(text)
                
                if 1 <= new_limit <= 1000:
                    # Используем старую функцию для постоянного лимита
                    success = await db.update_user_limit(user_id, chat_id, new_limit)
                    if success:
                        # Очищаем кэш
                        from ..handlers.group import user_empty_message_counters
                        empty_key = (user_id, chat_id)
                        if empty_key in user_empty_message_counters:
                            del user_empty_message_counters[empty_key]
                        
                        # Получаем текущий счетчик для сообщения
                        async with db.async_session() as session:
                            from sqlalchemy import select
                            from ..models.schemas import UserChatData
                            
                            result = await session.execute(
                                select(UserChatData)
                                .where(UserChatData.user_id == user_id)
                                .where(UserChatData.chat_id == chat_id)
                            )
                            user_chat_data = result.scalar_one_or_none()
                            current_count = user_chat_data.message_count if user_chat_data else 0
                        
                        await message.answer(
                            f"✅ Установлен постоянный лимит:\n"
                            f"• {new_limit} сообщений\n"
                            f"• без ограничения по времени\n\n"
                            f"📊 Счетчик сообщений сохранен: {current_count}\n"
                            f"🗑️ Счетчик пустых сообщений сброшен."
                        )
                        
                        await db.log_action(
                            "set_permanent_limit",
                            user_id=user_id,
                            chat_id=chat_id,
                            details=f"Постоянный лимит: {new_limit}"
                        )
                        
                        # Если пользователь был заблокирован - разблокируем
                        if user_chat_data and user_chat_data.is_muted:
                            try:
                                await message.bot.restrict_chat_member(
                                    chat_id=chat_id,
                                    user_id=user_id,
                                    permissions=types.ChatPermissions(
                                        can_send_messages=True,
                                        can_send_media_messages=True,
                                        can_send_polls=True,
                                        can_send_other_messages=True,
                                        can_add_web_page_previews=True,
                                        can_change_info=False,
                                        can_invite_users=True,
                                        can_pin_messages=False
                                    )
                                )
                                
                                async with db.async_session() as session:
                                    user_chat_data.is_muted = False
                                    user_chat_data.mute_until = None
                                    await session.commit()
                                
                                await message.answer(
                                    f"\n🔓 Пользователь автоматически разблокирован!"
                                )
                                
                                await db.log_action(
                                    "auto_unblock_with_permanent_limit",
                                    user_id=user_id,
                                    chat_id=chat_id,
                                    details=f"Авторазблокировка при установке постоянного лимита {new_limit}"
                                )
                                
                            except Exception as e:
                                print(f"⚠️ Не удалось автоматически разблокировать пользователя: {e}")
                        
                    else:
                        await message.answer("❌ Ошибка сохранения в БД")
                else:
                    await message.answer("❌ Лимит должен быть от 1 до 1000")
                    
            except ValueError:
                await message.answer("❌ Введите число от 1 до 1000 (или 0 для сброса, или лимит/дни)")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await db.log_action(
            "process_limit_error",
            user_id=user_id if 'user_id' in locals() else None,
            chat_id=chat_id if 'chat_id' in locals() else None,
            details=f"Ошибка: {str(e)}"
        )
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_exception_word))
async def process_exception_word(message: types.Message, state: FSMContext):
    """Обработка нового слова исключения"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_word = message.text.strip()
    
    if not new_word:
        await message.answer("❌ Слово не может быть пустым")
        return
    
    if len(new_word) > 50:
        await message.answer("❌ Слово слишком длинное (макс. 50 символов)")
        return
    
    try:
        data = await state.get_data()
        action_type = data.get("action_type", "add_exception")
        
        if action_type == "add_banned_word":
            # Добавляем запрещенное слово
            settings = await db.get_global_settings()
            if settings:
                if not hasattr(settings, 'default_banned_words'):
                    settings.default_banned_words = []
                
                if new_word.lower() not in [w.lower() for w in settings.default_banned_words]:
                    new_banned_words = settings.default_banned_words + [new_word]
                    
                    try:
                        settings.default_banned_words = new_banned_words
                        async with db.async_session() as session:
                            await session.merge(settings)
                            await session.commit()
                        
                        await message.answer(
                            f"✅ Добавлено запрещенное слово: {new_word}\n\n"
                            f"Теперь сообщения с этим словом будут вести к блокировке на 3 дня.\n"
                            f"Применяется ко всем чатам."
                        )
                    except Exception as e:
                        print(f"❌ Ошибка сохранения запрещенного слова: {e}")
                        await message.answer("❌ Ошибка сохранения")
                else:
                    await message.answer(f"ℹ️ Запрещенное слово {new_word} уже существует")
            else:
                await message.answer("❌ Ошибка: настройки не найдены")
                
        else:
            # Добавляем обычное исключение
            settings = await db.get_global_settings()
            if settings:
                if settings.default_exclude_words is None:
                    settings.default_exclude_words = []
                
                if new_word.lower() not in [w.lower() for w in settings.default_exclude_words]:
                    new_exceptions = settings.default_exclude_words + [new_word]
                    success = await db.update_global_exceptions(new_exceptions)
                    
                    if success:
                        await message.answer(
                            f"✅ Добавлено исключение: {new_word}\n\n"
                            f"Теперь сообщения с этим словом не будут учитываться.\n"
                            f"Применяется ко всем чатам."
                        )
                    else:
                        await message.answer("❌ Ошибка сохранения")
                else:
                    await message.answer(f"ℹ️ Исключение {new_word} уже существует")
            else:
                await message.answer("❌ Ошибка: настройки не найдены")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_empty_notification))
async def process_empty_notification(message: types.Message, state: FSMContext):
    """Обработка нового текста для пустых сообщений"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    try:
        await message.answer(
            f"✅ Текст уведомления обновлен!\n\n"
            f"Новый текст:\n{new_text}\n\n"
            f"(Временно: настройки не сохраняются в БД)"
        )
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_warning_notification))
async def process_warning_notification(message: types.Message, state: FSMContext):
    """Обработка нового текста предупреждения"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    if "{N}" not in new_text:
        await message.answer("⚠️ В тексте должна быть переменная {N} для количество оставшихся сообщений")
        return
    
    try:
        await message.answer(
            f"✅ Текст предупреждения обновлен!\n\n"
            f"Новый текст:\n{new_text}\n\n"
            f"(Временно: настройки не сохраняются в БД)"
        )
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_limit_notification))
async def process_limit_notification(message: types.Message, state: FSMContext):
    """Обработка нового текста при исчерпании лимита"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    try:
        await message.answer(
            f"✅ Текст уведомления обновлен!\n\n"
            f"Новый текст:\n{new_text}\n\n"
            f"(Временно: настройки не сохраняются в БД)"
        )
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_blocked_notification))
async def process_blocked_notification(message: types.Message, state: FSMContext):
    """Обработка нового текста для заблокированных"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    try:
        await message.answer(
            f"✅ Текст уведомления обновлен!\n\n"
            f"Новый текст:\n{new_text}\n\n"
            f"(Временно: настройки не сохраняются в БД)"
        )
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_contact_link))
async def process_contact_link(message: types.Message, state: FSMContext):
    """Обработка новой контактной ссылки"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_link = message.text.strip()
    
    if len(new_link) > 200:
        await message.answer("❌ Ссылка слишком длинная (макс. 200 символов)")
        return
    
    try:
        success = await db.update_global_settings(contact_link=new_link)
        
        if success:
            if new_link:
                await message.answer(
                    f"✅ Контактная ссылка обновлена!\n\n"
                    f"Новая ссылка:\n{new_link}"
                )
            else:
                await message.answer("✅ Контактная ссылка удалена")
        else:
            await message.answer("❌ Ошибка сохранения в БД")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()    
    from .commands import cmd_start
    await cmd_start(message, state)

# ===== ОБРАБОТКА НОВЫХ СОСТОЯНИЙ =====

@router.message(StateFilter(AdminStates.waiting_for_min_length))
async def process_min_length(message: types.Message, state: FSMContext):
    """Обработка новой минимальной длины сообщений"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    text = message.text.strip()
    
    if text.lower() == 'отмена':
        await message.answer("❌ Изменение отменено")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    try:
        new_length = int(text)
        
        if 5 <= new_length <= 100:
            settings = await db.get_global_settings()
            
            if not settings:
                await message.answer("❌ Настройки не найдены")
                await state.clear()
                return
            
            try:
                settings.default_min_message_length = new_length
                async with db.async_session() as session:
                    await session.merge(settings)
                    await session.commit()
                
                await message.answer(
                    f"✅ Минимальная длина сообщений изменена на {new_length} символов\n\n"
                    f"Сообщения короче {new_length} символов (без пробелов) "
                    f"не будут учитываться в счетчике."
                )
                
            except Exception as e:
                print(f"❌ Ошибка сохранения длины: {e}")
                await message.answer("❌ Ошибка сохранения")
        else:
            await message.answer("❌ Длина должна быть от 5 до 100 символов")
            
    except ValueError:
        await message.answer("❌ Введите число от 5 до 100")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

@router.message(StateFilter(AdminStates.waiting_for_test_text))
async def process_test_text(message: types.Message, state: FSMContext):
    """Обработка текста для тестирования длины сообщений"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    test_text = message.text.strip()
    
    if test_text.lower() == 'отмена':
        await message.answer("❌ Тест отменен")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    try:
        settings = await db.get_global_settings()
        current_length = getattr(settings, 'default_min_message_length', 20) if settings else 20
        
        # Считаем символы без пробелов
        text_without_spaces = ''.join(test_text.split())
        char_count = len(text_without_spaces)
        
        # Проверяем на запрещенные слова
        banned_words = []
        if settings and hasattr(settings, 'default_banned_words'):
            banned_words = settings.default_banned_words
        
        found_banned_words = []
        for banned_word in banned_words:
            # Ищем целые слова
            import re
            pattern = r'\b' + re.escape(banned_word.lower()) + r'\b'
            if re.search(pattern, test_text.lower()):
                found_banned_words.append(banned_word)
        
        # Формируем ответ
        text = (
            f"📊 <b>Результат проверки</b>\n\n"
            f"📝 <b>Текст:</b> {test_text[:100]}{'...' if len(test_text) > 100 else ''}\n\n"
            f"🔢 <b>Статистика:</b>\n"
            f"• Всего символов: {len(test_text)}\n"
            f"• Символов без пробелов: {char_count}\n"
            f"• Минимальная длина: {current_length}\n\n"
        )
        
        if char_count >= current_length:
            text += f"✅ <b>Результат:</b> Сообщение пройдет фильтр ({char_count} ≥ {current_length})\n"
        else:
            text += f"❌ <b>Результат:</b> Сообщение НЕ пройдет фильтр ({char_count} < {current_length})\n"
        
        if found_banned_words:
            text += f"\n🚫 <b>Обнаружены запрещенные слова:</b>\n"
            for word in found_banned_words:
                text += f"• {word}\n"
            text += f"\n⚠️ Такое сообщение приведет к блокировке на 3 дня!"
        
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)

    @router.callback_query(F.data.startswith("chat_manage:stats:"))
    async def chat_stats_callback(callback: types.CallbackQuery):
        """Статистика конкретного чата"""
        try:
            chat_id = int(callback.data.split(":")[2])
        
            # Получаем статистику напрямую
            async with db.async_session() as session:
                from sqlalchemy import select, func
                from ..models.schemas import UserChatData, User, Chat
            
                # Получаем чат
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
                if not chat:
                    await callback.answer("❌ Чат не найден")
                    return
            
                # Простая статистика
                # 1. Сообщения всего
                result = await session.execute(
                    select(func.sum(UserChatData.message_count))
                    .where(UserChatData.chat_id == chat_id)
                )
                total_msgs = result.scalar() or 0
            
                # 2. Активные пользователи
                result = await session.execute(
                    select(func.count(UserChatData.user_id.distinct()))
                    .where(UserChatData.chat_id == chat_id)
                    .where(UserChatData.message_count > 0)
                )
                active_users = result.scalar() or 0
            
                # 3. Заблокированные
                result = await session.execute(
                    select(func.count(UserChatData.id))
                    .where(UserChatData.chat_id == chat_id)
                    .where(UserChatData.is_muted == True)
                )
                blocked = result.scalar() or 0
            
                text = (
                    f"📊 <b>Статистика чата '{chat.title}'</b>\n\n"
                    f"📈 <b>Основные показатели:</b>\n"
                    f"• Сообщений всего: {total_msgs}\n"
                    f"• Активных пользователей: {active_users}\n"
                    f"• Заблокировано: {blocked}\n"
                    f"• Лимит чата: {chat.message_limit} сообщ./мес.\n\n"
                    f"📅 <b>Состояние:</b>\n"
                    f"• Активен: {'✅ Да' if chat.is_active else '❌ Нет'}\n"
                    f"• Исключений: {len(chat.exclude_words or [])}\n"
                    f"• Создан: {chat.created_at.strftime('%d.%m.%Y')}\n\n"
                    f"<i>Обновлено: {datetime.now().strftime('%H:%M')}</i>"
                )
            
                from ..keyboards.admin import get_back_to_menu_keyboard
                await callback.message.edit_text(text, 
                                           reply_markup=get_back_to_menu_keyboard(), 
                                           parse_mode="HTML")
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {e}")
        finally:
            await callback.answer()
@router.callback_query(F.data.startswith("search_user:"))
async def search_user_callback(callback: types.CallbackQuery, state: FSMContext):
    """Поиск пользователя по ID в админ-панели"""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        
        text = (
            "🔍 Поиск пользователя по ID\n\n"
            f"Чат ID: {chat_id}\n\n"
            "Отправьте ID пользователя для поиска:\n"
            "(можно получить через команду /id в чате)\n\n"
            "❌Отмена: отправьте 'отмена'"
        )
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
        await state.update_data(chat_id=chat_id, action="search_user")
        await state.set_state(AdminStates.waiting_for_user_search)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()
@router.message(StateFilter(AdminStates.waiting_for_user_search))
async def process_user_search(message: types.Message, state: FSMContext):
    """Обработка поиска пользователя"""
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        return
    
    search_text = message.text.strip()
    
    if search_text.lower() == 'отмена':
        await message.answer("❌ Поиск отменен")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    try:
        data = await state.get_data()
        chat_id = data.get("chat_id")
        search_type = data.get("search_type", "id")  # По умолчанию поиск по ID
        
        if not chat_id:
            await message.answer("❌ Ошибка: ID чата не найден")
            await state.clear()
            return
        
        # Ищем пользователей
        users_data = await db.search_users_in_chat(chat_id, search_text)
        
        if users_data:
            users_list = ""
            user_buttons = []
            
            for i, (user_chat_data, user) in enumerate(users_data[:15], 1):
                # Получаем данные с расчетом дней
                user_full_data = await db.get_user_data_with_days(user.id, chat_id)
                
                if user_full_data:
                    days_left = user_full_data['days_left']
                    is_custom = user_full_data['is_custom']
                    user_limit = user_full_data['user_limit']
                else:
                    days_left = 0
                    is_custom = False
                    user_limit = await db.get_user_limit(user.id, chat_id)
                
                # Форматирование
                username = f"@{user.username}" if user.username else f"ID:{user.id}"
                display_name = user.first_name or user.username or f"User {user.id}"
                
                if len(display_name) > 15:
                    display_name = display_name[:13] + ".."
                
                # Иконки статуса
                status_icon = "🔴" if user_chat_data.is_muted else "🟢"
                custom_icon = " ⭐" if is_custom else ""
                
                # Цветовое форматирование счетчика
                count_display = safe_format_count(user_chat_data.message_count, user_limit)
                
                # Дни до сброса
                days_display = format_days_left(days_left)
                
                users_list += (
                    f"{i}. {status_icon}{custom_icon} {display_name}\n"
                    f"   📊 {count_display} • 📅 {days_display}\n"
                    f"   👤 {username}\n\n"
                )
                
                user_buttons.append({
                    'user_chat_data': user_chat_data,
                    'user': user,
                    'display_name': display_name,
                    'is_custom': is_custom
                })
            
            text = (
                f"🔍 <b>Результаты поиска: \"{search_text}\"</b>\n\n"
                f"📊 Найдено пользователей: {len(users_data)}\n"
                f"⭐ - ручной лимит\n"
                f"📅 - дни до сброса\n\n"
                f"{users_list}"
                f"<i>Нажмите на номер пользователя для управления:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for i, user_data in enumerate(user_buttons[:10], 1):
                btn_text = f"{i}. {user_data['display_name'][:12]}"
                if len(user_data['display_name']) > 12:
                    btn_text = btn_text[:10] + ".."
                
                if user_data['is_custom']:
                    btn_text += " ⭐"
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"user_select:{user_data['user'].id}:{chat_id}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад к поиску",
                    callback_data=f"chat_manage:users:{chat_id}"
                ),
                types.InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="main_menu"
                ),
                width=2
            )
            
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        else:
            text = (
                f"🔍 <b>Результаты поиска: \"{search_text}\"</b>\n\n"
                f"❌ Пользователи не найдены\n\n"
                f"Попробуйте:\n"
                f"1. Другой поисковый запрос\n"
                f"2. Поиск по ID пользователя\n"
                f"3. Посмотреть всех пользователей (*)"
            )
            
            from ..keyboards.admin import get_back_to_menu_keyboard
            await message.answer(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)
async def ensure_user_in_chat(user_id: int, chat_id: int, username: str = None, 
                             first_name: str = None, last_name: str = None):
    """Гарантирует, что пользователь сохранен в чате (даже если message_count = 0)"""
    try:
        # Сохраняем пользователя
        user = await db.get_or_create_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        # Сохраняем чат
        chat = await db.get_or_create_chat(chat_id, "Unknown Chat")
        
        # Создаем запись пользователя в чате (если еще нет)
        user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
        
        return user_chat_data
        
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя: {e}")
        return None
    
@router.callback_query(F.data == "admin:notification_settings")
async def notification_settings_callback(callback: types.CallbackQuery):
    """Обработчик настроек уведомлений (в разработке)"""
    text = (
        "⚙️ <b>Настройки уведомлений</b>\n\n"
        "🔧 <b>Эта функция находится в разработке</b>\n\n"
        "В данный момент можно настроить уведомления:\n"
        "1. В файле конфигурации <code>config.py</code>\n"
        "2. Через редактирование БД\n\n"
        "Скоро будет доступно через интерфейс!"
    )
    
    await safe_edit_message(callback, text, get_back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer("⏳ Функция в разработке")

@router.callback_query(F.data.startswith("notifications:chat_edit_all:"))
async def chat_edit_all_notifications_callback(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование всех уведомлений для чата"""
    try:
        chat_id = int(callback.data.split(":")[2])
        chat = await db.get_chat_by_id(chat_id)
        
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        text = (
            f"✏️ <b>Редактирование всех уведомлений для чата</b>\n\n"
            f"💬 Чат: {chat.title}\n\n"
            f"<i>Отправьте JSON с настройками уведомлений:</i>\n\n"
            f"<b>Пример:</b>\n"
            f"<code>{json.dumps(config.DEFAULT_NOTIFICATIONS, ensure_ascii=False, indent=2)[:300]}...</code>\n\n"
            f"<i>Или 'отмена' для отмены</i>"
        )
        
        from ..keyboards.admin import get_back_to_menu_keyboard
        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
        
        await state.update_data(chat_id=chat_id, action="edit_all_notifications")
        await state.set_state(AdminStates.waiting_for_notification_text)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("notifications:chat_reset:"))
async def chat_reset_notifications_callback(callback: types.CallbackQuery):
    """Сброс уведомлений чата к глобальным"""
    try:
        chat_id = int(callback.data.split(":")[2])
        chat = await db.get_chat_by_id(chat_id)
        
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        # Сбрасываем уведомления (удаляем кастомные)
        success = await db.update_chat_notifications(chat_id, {})
        
        if success:
            await callback.answer("✅ Уведомления чата сброшены к глобальным")
            
            # Возвращаемся к меню уведомлений чата
            from .notifications import chat_notifications_callback
            await chat_notifications_callback(callback)
        else:
            await callback.answer("❌ Ошибка сброса")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_notification_text))
async def process_notification_text(message: types.Message, state: FSMContext):
    """Обработка нового текста уведомления"""
    if message.text.startswith('/'):
        return
    
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        await show_user_limits_message(message)
        return
    
    new_text = message.text
    
    if new_text.lower() == 'отмена':
        await message.answer("❌ Редактирование отменено")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
        return
    
    if len(new_text) > 500:
        await message.answer("❌ Текст слишком длинный (макс. 500 символов)")
        return
    
    try:
        data = await state.get_data()
        notify_type = data.get("notify_type")
        is_global = data.get("is_global", False)
        db_key = data.get("db_key")
        action = data.get("action")
        
        # Обработка JSON для массового редактирования
        if action == "edit_all_notifications":
            try:
                # Пытаемся распарсить JSON
                new_notifications = json.loads(new_text)
                chat_id = data.get("chat_id")
                
                if not chat_id:
                    await message.answer("❌ Ошибка: ID чата не найден")
                    await state.clear()
                    return
                
                # Проверяем структуру
                required_keys = ['empty_message', 'warning_3_messages', 'limit_exceeded', 
                               'user_blocked', 'empty_message_blocked', 'swear_word_blocked']
                
                for key in required_keys:
                    if key not in new_notifications:
                        await message.answer(f"❌ В JSON отсутствует ключ: {key}")
                        return
                
                # Сохраняем уведомления
                success = await db.update_chat_notifications(chat_id, new_notifications)
                
                if success:
                    await message.answer(f"✅ Все уведомления для чата обновлены!")
                else:
                    await message.answer("❌ Ошибка сохранения")
                    
            except json.JSONDecodeError:
                await message.answer("❌ Неверный формат JSON. Проверьте синтаксис.")
            except Exception as e:
                await message.answer(f"❌ Ошибка: {str(e)}")
            
            await state.clear()
            from .commands import cmd_start
            await cmd_start(message, state)
            return
        
        # Если db_key не передан, используем маппинг
        if not db_key:
            types_map = {
                "empty": "empty_message",
                "warning": "warning_3_messages", 
                "limit": "limit_exceeded",
                "blocked": "user_blocked",
                "empty_blocked": "empty_message_blocked",
                "swear_blocked": "swear_word_blocked"
            }
            
            if notify_type not in types_map:
                await message.answer("❌ Неизвестный тип уведомления")
                await state.clear()
                return
            
            db_key = types_map[notify_type]
        
        if is_global:
            # Сохраняем в глобальных настройках
            settings = await db.get_global_settings()
            if settings:
                if not settings.default_notifications:
                    settings.default_notifications = {}
                
                new_notifications = settings.default_notifications.copy()
                new_notifications[db_key] = new_text
                
                success = await db.update_global_notifications(new_notifications)
                
                if success:
                    await message.answer(f"✅ Глобальное уведомление '{notify_type}' обновлено!")
                else:
                    await message.answer("❌ Ошибка сохранения")
            else:
                await message.answer("❌ Настройки не найдены")
        else:
            # Сохраняем для конкретного чата
            chat_id = data.get("chat_id")
            if not chat_id:
                await message.answer("❌ Ошибка: ID чата не найден")
                await state.clear()
                return
            
            chat = await db.get_chat_by_id(chat_id)
            if not chat:
                await message.answer("❌ Чат не найден")
                await state.clear()
                return
            
            if not chat.custom_notifications:
                chat.custom_notifications = {}
            
            new_notifications = chat.custom_notifications.copy()
            new_notifications[db_key] = new_text
            
            success = await db.update_chat_notifications(chat_id, new_notifications)
            
            if success:
                await message.answer(f"✅ Уведомление для чата обновлено!")
            else:
                await message.answer("❌ Ошибка сохранения")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()
    from .commands import cmd_start
    await cmd_start(message, state)