from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..database import db
from ..utils.admin_check import is_admin
from .callbacks import show_user_limits_message

router = Router()


# В файл commands.py добавить:

@router.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    """Поиск чатов и пользователей"""
    if not is_admin(message.from_user.id):
        await show_user_limits_message(message)
        return
    
    text = (
        "🔍 <b>Поиск</b>\n\n"
        "Доступные команды поиска:\n\n"
        "• /search_chats - поиск чатов по названию или ID\n"
        "• В меню пользователей чата:\n"
        "  - * - показать всех пользователей\n"
        "  - ID - поиск по ID пользователя\n"
        "  - Имя - поиск по имени\n\n"
        "Для поиска чатов используйте кнопку ниже:"
    )
    
    from ..keyboards.admin import get_main_menu_keyboard
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    
async def main_menu_handler(message: types.Message):
    """Отправляет главное меню"""
    from ..utils.admin_check import is_admin
    from ..keyboards.admin import get_main_menu_keyboard
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await show_user_limits_message(message)
        return
    
    text = "👋 Добро пожаловать в панель управления!\n\nВыберите действие:"
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start - ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    await state.clear()
    from ..utils.admin_check import is_admin
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        # Показываем обычному пользователю только его лимиты
        await show_user_limits_message(message)
        return
    
    # Админам показываем полное меню
    await main_menu_handler(message)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help - ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        # Помощь для обычных пользователей
        text = (
            "❓ Помощь по использованию бота\n\n"
            
            "📝 Как это работает:\n"
            "1. Бот автоматически считает ваши сообщения в чатах\n"
            "2. У вас есть лимит сообщений в месяц\n"
            "3. При достижении лимита вы будете временно заблокированы\n"
            "4. Лимит сбрасывается 1-го числа каждого месяца\n\n"
            
            "👤 Ваши команды:\n"
            "• /start - Показать ваши лимиты\n"
            "• /help - Эта справка\n"
            "• /id - Узнать свой ID\n\n"
            
            "📞 Поддержка:\n"
            "• Для увеличения лимита обратитесь к администратору чата\n"
            "• Проблемы с ботом? Напишите владельцу бота"
        )
    else:
        # Помощь для администраторов
        text = (
            "❓ Помощь для администраторов\n\n"
            
            "👮‍♂️ Админ-команды:\n"
            "• /start - Главное меню\n"
            "• /help - Эта справка\n"
            "• /id - Узнать ID\n"
            "• /admin_stats - Статистика бота\n"
            "• /admin_list - Список администраторов\n"
            "• /export_stats - Экспорт статистики\n\n"
            
            "📊 Управление:\n"
            "Используйте меню /start для доступа ко всем функциям:\n"
            "• Управление лимитами\n"
            "• Список чатов\n"
            "• Настройки уведомлений\n"
            "• Исключения\n"
            "• Глобальные настройки\n"
            "• Статистика\n"
            "• Безопасность\n\n"
            
            "🔄 Автоматические функции:\n"
            "• Сброс счетчиков 1-го числа\n"
            "• Автоматическая блокировка\n"
            "• Авторазблокировка\n"
            "• Резервное копирование"
        )
    
    await message.answer(text)

@router.message(Command("id"))
async def cmd_id(message: types.Message):
    """Команда /id - ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    text = (
        f"👤 Ваш ID: `{user_id}`\n"
        f"💬 ID чата: `{chat_id}`\n"
    )
    
    if message.chat.type != "private":
        text += f"📝 Тип чата: {message.chat.type}\n"
        if message.chat.title:
            text += f"🏷️ Название чата: {message.chat.title}\n"
    
    if is_admin(user_id):
        text += f"\n👮‍♂️ Статус: Администратор бота"
    
    await message.answer(text)

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: types.Message):
    """Команда /admin_stats - статистика бота (только для админов) ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    try:
        from ..services.scheduler import get_scheduler_info
        
        stats = await db.get_general_statistics()
        scheduler_info = get_scheduler_info()
        
        text = (
            "📊 Статистика бота\n\n"
            f"📈 Основные показатели:\n"
            f"• Чатов: {stats.get('total_chats', 0)}\n"
            f"• Пользователей: {stats.get('total_users', 0)}\n"
            f"• Сообщений: {stats.get('total_messages', 0)}\n"
            f"• Заблокировано: {stats.get('blocked_users', 0)}\n\n"
            f"{scheduler_info}\n\n"
            f"⏰ Бот работает с: {stats.get('bot_started', 'Неизвестно')}"
        )
        
        await message.answer(text)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения статистики: {e}")

@router.message(Command("admin_list"))
async def cmd_admin_list(message: types.Message):
    """Команда /admin_list - список администраторов (только для админов) ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    try:
        from ..utils.admin_check import list_admins
        
        text = list_admins()
        await message.answer(text)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения списка администраторов: {e}")

@router.message(Command("export_stats"))
async def cmd_export_stats(message: types.Message):
    """Команда /export_stats - экспорт статистики (только для админов) ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    await message.answer(
        "📤 Экспорт статистики\n\n"
        "Доступные форматы:\n"
        "• CSV файл: /export_stats_csv\n"
        "• Excel файл: /export_stats_excel (в разработке)\n\n"
        "Или используйте меню /start для получения статистики"
    )

@router.message(Command("export_stats_csv"))
async def cmd_export_stats_csv(message: types.Message):
    """Команда /export_stats_csv - экспорт в CSV (только для админов) ТОЛЬКО в личных сообщениях"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return  # Игнорируем команду в группах
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    try:
        # Здесь будет логика экспорта в CSV
        await message.answer(
            "📤 Экспорт в CSV\n\n"
            "Функция экспорта статистики в CSV файл находится в разработке.\n"
            "Используйте меню /start → Статистика для просмотра текущих данных."
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {e}")

@router.message(Command("test_save"))
async def cmd_test_save(message: types.Message):
    """Тест сохранения уведомлений"""
    try:
        # Тестируем сохранение
        test_data = {
            "empty_message": "ТЕСТ: Пустые сообщения запрещены",
            "warning_3_messages": "ТЕСТ: Осталось {N} сообщений",
            "limit_exceeded": "ТЕСТ: Лимит исчерпан {contact_link}",
            "user_blocked": "ТЕСТ: Вы заблокированы"
        }
        
        success = await db.update_global_notifications(test_data)
        
        if success:
            await message.answer("✅ Тестовые данные сохранены\n\nПроверяем сохранение...")
            
            # Даем время на сохранение
            import asyncio
            await asyncio.sleep(1)
            
            # Получаем сохраненные данные
            settings = await db.get_global_settings()
            if settings and settings.default_notifications:
                result = ""
                for key, value in settings.default_notifications.items():
                    result += f"{key}: {value[:30]}...\n"
                
                await message.answer(f"📊 Сохраненные данные:\n\n{result}")
            else:
                await message.answer("❌ Данные не найдены после сохранения")
        else:
            await message.answer("❌ Ошибка при сохранении")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")