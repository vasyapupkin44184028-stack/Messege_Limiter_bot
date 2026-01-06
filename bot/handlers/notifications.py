from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from datetime import datetime

from ..database import db
from ..states import AdminStates
from ..config import config
from ..utils.admin_check import is_admin

router = Router()

@router.callback_query(F.data == "notifications:manage")
async def manage_notifications_callback(callback: types.CallbackQuery):
    """Управление уведомлениями с выбором типа"""
    try:
        text = (
            "⚙️ <b>Управление уведомлениями</b>\n\n"
            "Выберите тип уведомлений для управления:\n\n"
            "• <b>Глобальные уведомления</b> - применяются ко всем чатам\n"
            "• <b>Уведомления для чата</b> - только для выбранного чата\n"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="🌐 Глобальные уведомления",
                callback_data="notifications:global"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="💬 Уведомления для чата",
                callback_data="notifications:chat_select"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="admin:notification_settings"
            ),
            types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            ),
            width=2
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "notifications:global")
async def global_notifications_callback(callback: types.CallbackQuery):
    """Управление глобальными уведомлениями"""
    try:
        settings = await db.get_global_settings()
        
        if settings and settings.default_notifications:
            notifications = settings.default_notifications
        else:
            notifications = config.DEFAULT_NOTIFICATIONS
        
        text = (
            "🌐 <b>Глобальные уведомления</b>\n\n"
            
            "📝 <b>Что это:</b>\n"
            "Эти уведомления применяются ко ВСЕМ чатам.\n\n"
            
            "📋 <b>Текущие уведомления:</b>\n\n"
            
            f"1. 🗑️ <b>Пустые сообщения (предупреждение):</b>\n"
            f"{notifications.get('empty_message', 'Нет текста')[:60]}...\n\n"
            
            f"2. ⚠️ <b>Предупреждение (3 сообщение):</b>\n"
            f"{notifications.get('warning_3_messages', 'Нет текста')[:60]}...\n\n"
            
            f"3. 🚫 <b>Лимит исчерпан:</b>\n"
            f"{notifications.get('limit_exceeded', 'Нет текста')[:60]}...\n\n"
            
            f"4. 🔒 <b>Заблокированным (общее):</b>\n"
            f"{notifications.get('user_blocked', 'Нет текста')[:60]}...\n\n"
            
            f"5. 🗑️ <b>Блокировка за пустые сообщения:</b>\n"
            f"{notifications.get('empty_message_blocked', 'Нет текста')[:60]}...\n\n"
            
            f"6. 🚫 <b>Блокировка за маты:</b>\n"
            f"{notifications.get('swear_word_blocked', 'Нет текста')[:60]}...\n\n"
            
            "<i>Переменные в текстах:</i>\n"
            "• {N} - оставшееся количество сообщений\n"
            "• {contact_link} - контакт для покупки\n"
            "• {mute_until} - дата разблокировки\n"
            "• {banned_word} - обнаруженное запрещенное слово\n\n"
            
            "<i>Выберите уведомление для редактирования:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="🗑️ Пустые (предупреждение)",
                callback_data="notify:global:empty"
            ),
            types.InlineKeyboardButton(
                text="⚠️ Предупреждение (3)",
                callback_data="notify:global:warning"
            ),
            width=2
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🚫 Лимит исчерпан",
                callback_data="notify:global:limit"
            ),
            types.InlineKeyboardButton(
                text="🔒 Заблокированным",
                callback_data="notify:global:blocked"
            ),
            width=2
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🗑️ Блокировка пустых",
                callback_data="notify:global:empty_blocked"
            ),
            types.InlineKeyboardButton(
                text="🚫 Блокировка матов",
                callback_data="notify:global:swear_blocked"
            ),
            width=2
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить к умолчанию",
                callback_data="notifications:global_reset"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="notifications:manage"
            ),
            types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            ),
            width=2
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("notify:global:"))
async def edit_global_notification_callback(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование глобального уведомления"""
    try:
        notify_type = callback.data.split(":")[2]
        
        types_map = {
            "empty": ("пустых сообщений (предупреждение)", "empty_message"),
            "warning": ("предупреждения (3 сообщение)", "warning_3_messages"),
            "limit": ("лимита исчерпан", "limit_exceeded"),
            "blocked": ("заблокированным пользователям", "user_blocked"),
            "empty_blocked": ("блокировки за пустые сообщения", "empty_message_blocked"),
            "swear_blocked": ("блокировки за маты", "swear_word_blocked")
        }
        
        if notify_type not in types_map:
            await callback.answer("❌ Неизвестный тип уведомления")
            return
        
        display_name, db_key = types_map[notify_type]
        
        settings = await db.get_global_settings()
        if settings and settings.default_notifications:
            current_text = settings.default_notifications.get(db_key, "")
        else:
            current_text = config.DEFAULT_NOTIFICATIONS.get(db_key, "")
        
        # Определяем доступные переменные для каждого типа
        variables_text = ""
        if notify_type == "warning":
            variables_text = "• {N} - оставшееся количество сообщений\n"
        elif notify_type == "limit":
            variables_text = "• {contact_link} - контакт для покупки\n"
        elif notify_type == "empty_blocked":
            variables_text = "• {mute_until} - дата разблокировки\n"
        elif notify_type == "swear_blocked":
            variables_text = "• {banned_word} - обнаруженное запрещенное слово\n• {mute_until} - дата разблокировки\n"
        else:
            variables_text = "• (специфичных переменных нет)\n"
        
        text = (
            f"✏️ <b>Редактирование глобального уведомления</b>\n\n"
            f"📝 <b>Тип:</b> {display_name}\n\n"
            f"<i>Отправьте новый текст уведомления:</i>\n\n"
            f"<b>Доступные переменные:</b>\n"
            f"{variables_text}"
            f"<b>Текущий текст:</b>\n"
            f"{current_text}\n\n"
            f"<i>Отправьте новый текст или 'отмена' для отмены</i>"
        )
        
        from ..keyboards.admin import get_back_to_menu_keyboard
        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
        
        await state.update_data(notify_type=notify_type, is_global=True, db_key=db_key)
        await state.set_state(AdminStates.waiting_for_notification_text)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "notifications:global_reset")
async def global_notifications_reset_callback(callback: types.CallbackQuery):
    """Сброс глобальных уведомлений к умолчанию"""
    try:
        success = await db.update_global_notifications(config.DEFAULT_NOTIFICATIONS)
        
        if success:
            await callback.answer("✅ Уведомления сброшены к умолчанию")
            await global_notifications_callback(callback)
        else:
            await callback.answer("❌ Ошибка сброса уведомлений")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "notifications:chat_select")
async def chat_select_notifications_callback(callback: types.CallbackQuery):
    """Выбор чата для управления уведомлениями"""
    try:
        chats = await db.get_all_chats()
        
        if chats:
            chat_list = ""
            chat_buttons = []
            
            for i, chat in enumerate(chats[:15], 1):
                icon = "👥" if chat.id < -100 else "💬"
                status = "🟢" if chat.is_active else "🔴"
                
                chat_list += f"{i}. {icon} {chat.title[:25]} {status}\n"
                chat_list += f"   ID: <code>{chat.id}</code>\n\n"
                
                chat_buttons.append({
                    'id': chat.id,
                    'title': chat.title[:20],
                    'icon': icon
                })
            
            text = (
                f"💬 <b>Выбор чата для настроек уведомлений</b>\n\n"
                f"Всего чатов: {len(chats)}\n\n"
                f"{chat_list}"
                f"<i>Выберите чат:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for chat in chat_buttons[:10]:
                display_text = f"{chat['icon']} {chat['title']}"
                if len(display_text) > 25:
                    display_text = display_text[:23] + ".."
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=display_text,
                        callback_data=f"notifications:chat:{chat['id']}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="notifications:manage"
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
                "💬 <b>Выбор чата для уведомлений</b>\n\n"
                "😕 Чатов не найдено\n\n"
                "Сначала добавьте бота в чат и сделайте его администратором."
            )
            
            from ..keyboards.admin import get_back_to_menu_keyboard
            await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("notifications:chat:"))
async def chat_notifications_callback(callback: types.CallbackQuery):
    """Управление уведомлениями для конкретного чата"""
    try:
        chat_id = int(callback.data.split(":")[2])
        chat = await db.get_chat_by_id(chat_id)
        
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        # Получаем уведомления чата (или глобальные если нет кастомных)
        notifications = await db.get_chat_notifications(chat_id)
        
        text = (
            f"💬 <b>Уведомления для чата '{chat.title}'</b>\n\n"
            
            "📝 <b>Текущие уведомления:</b>\n\n"
            
            f"1. 🗑️ <b>Пустые сообщения:</b>\n"
            f"{notifications.get('empty_message', 'По умолчанию')[:50]}...\n\n"
            
            f"2. ⚠️ <b>Предупреждение:</b>\n"
            f"{notifications.get('warning_3_messages', 'По умолчанию')[:50]}...\n\n"
            
            f"3. 🚫 <b>Лимит исчерпан:</b>\n"
            f"{notifications.get('limit_exceeded', 'По умолчанию')[:50]}...\n\n"
            
            f"4. 🔒 <b>Заблокированным:</b>\n"
            f"{notifications.get('user_blocked', 'По умолчанию')[:50]}...\n\n"
            
            f"5. 🗑️ <b>Блокировка за пустые:</b>\n"
            f"{notifications.get('empty_message_blocked', 'По умолчанию')[:50]}...\n\n"
            
            f"6. 🚫 <b>Блокировка за маты:</b>\n"
            f"{notifications.get('swear_word_blocked', 'По умолчанию')[:50]}...\n\n"
            
            "<i>Выберите действие:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="✏️ Редактировать все",
                callback_data=f"notifications:chat_edit_all:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить к глобальным",
                callback_data=f"notifications:chat_reset:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад к выбору",
                callback_data="notifications:chat_select"
            ),
            types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            ),
            width=2
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()