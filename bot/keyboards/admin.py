from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_exceptions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления исключениями"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔧 Управление исключениями",
            callback_data="exceptions:manage"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить исключение",
            callback_data="exceptions:add"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сбросить к умолчанию",
            callback_data="exceptions:reset"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Управление лимитами",
            callback_data="admin:global_limits"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📋 Список чатов", 
            callback_data="admin:chat_list"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🏗️ В разработке",
            callback_data="admin:notification_settings_dev"
        ),
        InlineKeyboardButton(
            text="🔧 Исключения",
            callback_data="admin:exceptions"
        ),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🌐 Глобальные настройки",
            callback_data="admin:global_settings"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📈 Статистика",
            callback_data="admin:statistics"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск чатов", 
            callback_data="admin:search_chats"
        )
    )    



    builder.row(
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data="admin:help"
        ),
        InlineKeyboardButton(
            text="🛡️ Безопасность",
            callback_data="admin:security"
        ),
        width=2
    )
    
    return builder.as_markup()

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    return builder.as_markup()

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек уведомлений (в разработке)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📝 Пустые сообщения",
            callback_data="notify:empty"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⚠️ Предупреждение (3 сообщение)",
            callback_data="notify:warning"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🚫 Лимит исчерпан",
            callback_data="notify:limit"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔒 Заблокированным",
            callback_data="notify:blocked"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="main_menu"
        ),
        InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="main_menu"
        ),
        width=2
    )
    
    return builder.as_markup()

def get_exceptions_list_keyboard(exceptions: list) -> InlineKeyboardMarkup:
    """Клавиатура списка исключений"""
    builder = InlineKeyboardBuilder()
    
    for word in exceptions[:15]:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {word[:20]}",
                callback_data=f"exception_remove:{word}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить новое",
            callback_data="exceptions:add"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:exceptions"
        ),
        InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="main_menu"
        ),
        width=2
    )
    
    return builder.as_markup()

def get_chats_list_keyboard(chats: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком чатов"""
    builder = InlineKeyboardBuilder()
    
    for chat in chats[:10]:
        display_text = f"{chat['icon']} {chat['title'][:20]}"
        if len(chat['title']) > 20:
            display_text = display_text[:18] + ".."
        
        builder.row(
            InlineKeyboardButton(
                text=display_text,
                callback_data=f"chat_select:{chat['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()

def get_chat_management_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретным чатом"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить лимит",
            callback_data=f"chat_manage:limit:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="👥 Показать пользователей",
            callback_data=f"chat_manage:users:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔧 Исключения чата",
            callback_data=f"chat_manage:exceptions:{chat_id}"
        )
        # Убрали кнопку уведомлений для чата - в разработке
        # InlineKeyboardButton(
        #     text="⚙️ Уведомления чата",
        #     callback_data=f"chat_manage:notifications:{chat_id}"
        # ),
        # width=2
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Вкл/Выкл бота",
            callback_data=f"chat_manage:toggle:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку чатов",
            callback_data="admin:chat_list"
        ),
        InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="main_menu"
        ),
        width=2
    )
    
    return builder.as_markup()

def get_global_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура глобальных настроек"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔗 Изменить контактную ссылку",
            callback_data="settings:contact"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Изменить лимит по умолчанию",
            callback_data="admin:global_limits"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Автосброс лимитов",
            callback_data="settings:auto_reset"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()

def get_user_management_keyboard(user_id: int, chat_id: int, current_limit: int = None):
    """Клавиатура управления конкретным пользователем"""
    builder = InlineKeyboardBuilder()
    
    limit_text = f"✏️ Изменить лимит ({current_limit if current_limit else 'авто'})"
    builder.row(
        InlineKeyboardButton(
            text=limit_text,
            callback_data=f"user_limit:{user_id}:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сбросить лимит",
            callback_data=f"user_reset_limit:{user_id}:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔓 Разблокировать",
            callback_data=f"user_unblock:{user_id}:{chat_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к чату",
            callback_data=f"chat_select:{chat_id}"
        ),
        InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="main_menu"
        ),
        width=2
    )
    
    return builder.as_markup()

def get_statistics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура статистики"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Общая статистика",
            callback_data="stats:general"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="👥 Статистика пользователей",
            callback_data="stats:users"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💬 Статистика чатов",
            callback_data="stats:chats"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📅 Ежемесячная статистика",
            callback_data="stats:monthly"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()

def get_security_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура безопасности"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🛡️ Настройки безопасности",
            callback_data="security:settings"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="👮‍♂️ Администраторы",
            callback_data="security:admins"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🚫 Заблокированные",
            callback_data="security:blocked"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📋 Логи действий",
            callback_data="security:logs"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()