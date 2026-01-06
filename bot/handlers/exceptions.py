import re
import traceback
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from datetime import datetime
from ..database import db
from ..states import AdminStates
from ..config import config
from ..utils.admin_check import is_admin

router = Router()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

async def get_banned_words_for_chat(chat_id: int) -> list:
    """Получает список запрещенных слов для чата из БД"""
    try:
        # Получаем настройки чата
        chat = await db.get_chat_by_id(chat_id)
        if chat and hasattr(chat, 'banned_words') and chat.banned_words:
            return chat.banned_words
        
        # Или глобальные настройки
        settings = await db.get_global_settings()
        if settings and hasattr(settings, 'default_banned_words') and settings.default_banned_words:
            return settings.default_banned_words
        
        # Или конфиг по умолчанию
        if hasattr(config, 'DEFAULT_BANNED_WORDS'):
            return config.DEFAULT_BANNED_WORDS
        
        # Базовый список запрещенных слов
        return ["хуй", "пизда", "еблан", "мудак", "сука", "блять", 
                "хуесос", "говно", "залупа", "пенис", "вагина", "секс",
                "ебать", "выебан", "дрочить", "конча", "сперма"]
        
    except Exception as e:
        print(f"⚠️ Ошибка получения запрещенных слов: {e}")
        return []

async def get_min_message_length(chat_id: int) -> int:
    """Получает минимальную длину сообщения для чата"""
    try:
        # Получаем настройки чата
        chat = await db.get_chat_by_id(chat_id)
        if chat and hasattr(chat, 'min_message_length') and chat.min_message_length:
            return chat.min_message_length
        
        # Или глобальные настройки
        settings = await db.get_global_settings()
        if settings and hasattr(settings, 'default_min_message_length') and settings.default_min_message_length:
            return settings.default_min_message_length
        
        # По умолчанию 20 символов
        return 20
        
    except Exception as e:
        print(f"⚠️ Ошибка получения минимальной длины: {e}")
        return 20

# ===== ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ ИСКЛЮЧЕНИЯМИ =====

# В функции manage_exceptions_callback измените кнопку "Назад":

@router.callback_query(F.data == "exceptions:manage")
async def manage_exceptions_callback(callback: types.CallbackQuery):
    """Управление исключениями с выбором типа"""
    try:
        text = (
            "🔧 <b>Управление исключениями и фильтрами</b>\n\n"
            "Выберите тип настроек для управления:\n\n"
            "• <b>Глобальные исключения</b> - слова, которые не учитываются в счетчике\n"
            "• <b>Запрещенные слова</b> - слова, которые ведут к блокировке\n"
            "• <b>Настройки длины</b> - минимальная длина сообщений\n"
            "• <b>Настройки для чата</b> - индивидуальные настройки для чатов\n"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="🌐 Глобальные исключения",
                callback_data="exceptions:global"
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
                text="📏 Настройки длины",
                callback_data="exceptions:length_settings"
            )
        )
        
        '''builder.row(
            types.InlineKeyboardButton(
                text="💬 Для конкретного чата",
                callback_data="exceptions:chat_select"
            )
        )'''
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="main_menu"  # Изменено с "admin:exceptions" на "main_menu"
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

# ===== ГЛОБАЛЬНЫЕ ИСКЛЮЧЕНИЯ =====

@router.callback_query(F.data == "exceptions:global")
async def global_exceptions_callback(callback: types.CallbackQuery):
    """Управление глобальными исключениями"""
    try:
        settings = await db.get_global_settings()
        
        if settings:
            exceptions = settings.default_exclude_words
            use_regex = settings.default_exclude_use_regex
        else:
            exceptions = config.DEFAULT_EXCLUDE_WORDS
            use_regex = config.DEFAULT_EXCLUDE_USE_REGEX
        
        exceptions_text = "\n".join([f"• {word}" for word in exceptions[:20]])
        
        if len(exceptions) > 20:
            exceptions_text += f"\n\n... и еще {len(exceptions) - 20} слов"
        
        regex_status = "✅ Включено" if use_regex else "❌ Выключено"
        
        text = (
            "🌐 <b>Глобальные исключения</b>\n\n"
            
            "📝 <b>Что это:</b>\n"
            "Эти слова/фразы не учитываются в счетчике сообщений.\n"
            "Применяются ко ВСЕМ чатам.\n\n"
            
            f"🔧 <b>Использование regex:</b> {regex_status}\n\n"
            
            "📋 <b>Текущие исключения:</b>\n"
            f"{exceptions_text}\n\n"
            
            "<i>Выберите действие:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="📝 Редактировать список",
                callback_data="exceptions:global_list"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🧮 Вкл/Выкл regex",
                callback_data="exceptions:global_toggle_regex"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить к умолчанию",
                callback_data="exceptions:global_reset"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="➕ Добавить новое",
                callback_data="exceptions:add"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="exceptions:manage"
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

@router.callback_query(F.data == "exceptions:global_list")
async def global_exceptions_list_callback(callback: types.CallbackQuery):
    """Список глобальных исключений для редактирования"""
    try:
        settings = await db.get_global_settings()
        exceptions = settings.default_exclude_words if settings else config.DEFAULT_EXCLUDE_WORDS
        
        if exceptions:
            exceptions_text = "\n".join([f"{i+1}. {word}" for i, word in enumerate(exceptions[:25])])
            
            if len(exceptions) > 25:
                exceptions_text += f"\n\n... и еще {len(exceptions) - 25} слов"
            
            text = (
                "📝 <b>Глобальные исключения - список</b>\n\n"
                f"{exceptions_text}\n\n"
                "<i>Нажмите на слово для удаления:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for word in exceptions[:20]:
                display_text = f"❌ {word[:25]}"
                if len(word) > 25:
                    display_text = display_text[:23] + ".."
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=display_text,
                        callback_data=f"exception_remove:{word}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="➕ Добавить новое",
                    callback_data="exceptions:add"
                )
            )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="exceptions:global"
                ),
                types.InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="main_menu"
                ),
                width=2
            )
            
        else:
            text = (
                "📝 <b>Глобальные исключения</b>\n\n"
                "Список пуст.\n\n"
                "<i>Добавьте слова, которые не должны учитываться в счетчике сообщений.</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="➕ Добавить исключение",
                    callback_data="exceptions:add"
                )
            )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="exceptions:global"
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

@router.callback_query(F.data.startswith("exception_remove:"))
async def exception_remove_callback(callback: types.CallbackQuery):
    """Удаление исключения"""
    try:
        word = callback.data.split(":", 1)[1]
        
        settings = await db.get_global_settings()
        if settings:
            if settings.default_exclude_words:
                new_exceptions = [w for w in settings.default_exclude_words if w.lower() != word.lower()]
                success = await db.update_global_exceptions(new_exceptions)
                if success:
                    await callback.answer(f"✅ Удалено: {word}")
                else:
                    await callback.answer("❌ Ошибка удаления")
            else:
                await callback.answer("⚠️ Нет исключений для удаления")
        else:
            await callback.answer("⚠️ Настройки не найдены")
        
        await global_exceptions_list_callback(callback)
        
    except Exception as e:
        await callback.answer("❌ Ошибка удаления")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:add")
async def exceptions_add_callback(callback: types.CallbackQuery, state: FSMContext):
    """Добавление нового исключения"""
    text = (
        "➕ <b>Добавление нового исключения</b>\n\n"
        
        "Отправьте слово или фразу для добавления в исключения:\n\n"
        
        "📝 <b>Примеры:</b>\n"
        "• привет\n"
        "• спасибо\n"
        "• цена?\n"
        "• как дела?\n\n"
        
        "⚙️ <b>Как работает:</b>\n"
        "Сообщения с этими словами не учитываются в счетчике.\n\n"
        
        "❌ <b>Отмена:</b> отправьте 'отмена'"
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="exceptions:global"
        )
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_exception_word)
    await callback.answer()

@router.callback_query(F.data == "exceptions:global_toggle_regex")
async def toggle_global_regex_callback(callback: types.CallbackQuery):
    """Переключение regex для глобальных исключений"""
    try:
        settings = await db.get_global_settings()
        
        if not settings:
            await callback.answer("❌ Настройки не найдены")
            return
        
        new_value = not settings.default_exclude_use_regex
        success = await db.update_global_exceptions(
            settings.default_exclude_words,
            new_value
        )
        
        if success:
            status = "включено" if new_value else "выключено"
            await callback.answer(f"✅ Использование regex {status}")
            await global_exceptions_callback(callback)
        else:
            await callback.answer("❌ Ошибка обновления")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:global_reset")
async def exceptions_reset_callback(callback: types.CallbackQuery):
    """Сброс исключений к умолчанию"""
    try:
        success = await db.update_global_exceptions(config.DEFAULT_EXCLUDE_WORDS)
        if success:
            await callback.answer("✅ Исключения сброшены к умолчанию")
            await global_exceptions_callback(callback)
        else:
            await callback.answer("❌ Ошибка сброса")
    except Exception as e:
        await callback.answer("❌ Ошибка сброса")
    finally:
        await callback.answer()

# ===== ЗАПРЕЩЕННЫЕ СЛОВА =====

@router.callback_query(F.data == "exceptions:banned_words")
async def banned_words_callback(callback: types.CallbackQuery):
    """Управление запрещенными словами"""
    try:
        settings = await db.get_global_settings()
        
        # Получаем запрещенные слова из БД
        if settings and hasattr(settings, 'default_banned_words'):
            banned_words = settings.default_banned_words
        else:
            # Проверяем, есть ли атрибут в конфиге
            if hasattr(config, 'DEFAULT_BANNED_WORDS'):
                banned_words = config.DEFAULT_BANNED_WORDS
            else:
                banned_words = ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
        
        # Проверяем настройку чувствительности к регистру
        case_sensitive = getattr(settings, 'banned_words_case_sensitive', True) if settings else True
        
        banned_text = "\n".join([f"• {word}" for word in banned_words[:20]])
        
        if len(banned_words) > 20:
            banned_text += f"\n\n... и еще {len(banned_words) - 20} слов"
        
        case_status = "✅ Включена" if case_sensitive else "❌ Выключена"
        
        text = (
            "🚫 <b>Управление запрещенными словами</b>\n\n"
            
            "📝 <b>Что это:</b>\n"
            "Эти слова ведут к автоматической блокировке на 3 дня.\n"
            "Применяются ко ВСЕМ чатам.\n\n"
            
            f"🔤 <b>Чувствительность к регистру:</b> {case_status}\n\n"
            
            "⚠️ <b>Внимание:</b>\n"
            "Слова проверяются как целые слова (с границами).\n"
            "Например, 'хуй' будет заблокировано, но 'застрахуй' - нет.\n\n"
            
            "📋 <b>Текущие запрещенные слова:</b>\n"
            f"{banned_text}\n\n"
            
            "<i>Выберите действие:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="📝 Редактировать список",
                callback_data="exceptions:banned_list"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔤 Вкл/Выкл регистр",
                callback_data="exceptions:banned_toggle_case"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="➕ Добавить слово",
                callback_data="exceptions:banned_add"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить к умолчанию",
                callback_data="exceptions:banned_reset"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="exceptions:manage"
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

@router.callback_query(F.data == "exceptions:banned_list")
async def banned_words_list_callback(callback: types.CallbackQuery):
    """Список запрещенных слов для редактирования"""
    try:
        settings = await db.get_global_settings()
        
        if settings and hasattr(settings, 'default_banned_words'):
            banned_words = settings.default_banned_words
        else:
            banned_words = ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
        
        if banned_words:
            banned_text = "\n".join([f"{i+1}. {word}" for i, word in enumerate(banned_words[:25])])
            
            if len(banned_words) > 25:
                banned_text += f"\n\n... и еще {len(banned_words) - 25} слов"
            
            text = (
                "📝 <b>Запрещенные слова - список</b>\n\n"
                f"{banned_text}\n\n"
                "<i>Нажмите на слово для удаления:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for word in banned_words[:20]:
                display_text = f"🚫 {word[:25]}"
                if len(word) > 25:
                    display_text = display_text[:23] + ".."
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=display_text,
                        callback_data=f"banned_remove:{word}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="➕ Добавить новое",
                    callback_data="exceptions:banned_add"
                )
            )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="exceptions:banned_words"
                ),
                types.InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="main_menu"
                ),
                width=2
            )
            
        else:
            text = (
                "📝 <b>Запрещенные слова</b>\n\n"
                "Список пуст.\n\n"
                "<i>Добавьте слова, которые должны приводить к блокировке пользователей.</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="➕ Добавить запрещенное слово",
                    callback_data="exceptions:banned_add"
                )
            )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="exceptions:banned_words"
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

@router.callback_query(F.data.startswith("banned_remove:"))
async def banned_word_remove_callback(callback: types.CallbackQuery):
    """Удаление запрещенного слова"""
    try:
        word = callback.data.split(":", 1)[1]
        
        settings = await db.get_global_settings()
        if settings:
            if hasattr(settings, 'default_banned_words') and settings.default_banned_words:
                new_banned_words = [w for w in settings.default_banned_words if w.lower() != word.lower()]
                
                # Обновляем атрибут (нужно будет добавить метод в БД)
                try:
                    settings.default_banned_words = new_banned_words
                    async with db.async_session() as session:
                        await session.merge(settings)
                        await session.commit()
                    
                    await callback.answer(f"✅ Удалено запрещенное слово: {word}")
                except Exception as e:
                    print(f"❌ Ошибка удаления запрещенного слова: {e}")
                    await callback.answer("❌ Ошибка удаления")
            else:
                await callback.answer("⚠️ Нет запрещенных слов для удаления")
        else:
            await callback.answer("⚠️ Настройки не найдены")
        
        await banned_words_list_callback(callback)
        
    except Exception as e:
        await callback.answer("❌ Ошибка удаления")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:banned_add")
async def banned_word_add_callback(callback: types.CallbackQuery, state: FSMContext):
    """Добавление нового запрещенного слова"""
    text = (
        "➕ <b>Добавление запрещенного слова</b>\n\n"
        
        "Отправьте слово для добавления в список запрещенных:\n\n"
        
        "📝 <b>Примеры:</b>\n"
        "• хуй\n"
        "• пизда\n"
        "• еблан\n\n"
        
        "⚙️ <b>Как работает:</b>\n"
        "Сообщения с этими словами ведут к блокировке на 3 дня.\n"
        "Проверяется как целое слово (с границами).\n\n"
        
        "❌ <b>Отмена:</b> отправьте 'отмена'"
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="exceptions:banned_words"
        )
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.update_data(action_type="add_banned_word")
    await state.set_state(AdminStates.waiting_for_exception_word)
    await callback.answer()

@router.callback_query(F.data == "exceptions:banned_toggle_case")
async def toggle_banned_case_callback(callback: types.CallbackQuery):
    """Переключение чувствительности к регистру для запрещенных слов"""
    try:
        settings = await db.get_global_settings()
        
        if not settings:
            await callback.answer("❌ Настройки не найдены")
            return
        
        # Переключаем настройку
        current_value = getattr(settings, 'banned_words_case_sensitive', True)
        new_value = not current_value
        
        # Обновляем в БД
        try:
            settings.banned_words_case_sensitive = new_value
            async with db.async_session() as session:
                await session.merge(settings)
                await session.commit()
            
            status = "включена" if new_value else "выключена"
            await callback.answer(f"✅ Чувствительность к регистру {status}")
            await banned_words_callback(callback)
        except Exception as e:
            print(f"❌ Ошибка обновления настроек регистра: {e}")
            await callback.answer("❌ Ошибка обновления")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:banned_reset")
async def banned_words_reset_callback(callback: types.CallbackQuery):
    """Сброс запрещенных слов к умолчанию"""
    try:
        settings = await db.get_global_settings()
        
        if not settings:
            await callback.answer("❌ Настройки не найдены")
            return
        
        # Сбрасываем к дефолтным значениям
        default_words = ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
        
        try:
            settings.default_banned_words = default_words
            async with db.async_session() as session:
                await session.merge(settings)
                await session.commit()
            
            await callback.answer("✅ Запрещенные слова сброшены к умолчанию")
            await banned_words_callback(callback)
        except Exception as e:
            print(f"❌ Ошибка сброса запрещенных слов: {e}")
            await callback.answer("❌ Ошибка сброса")
            
    except Exception as e:
        await callback.answer("❌ Ошибка сброса")
    finally:
        await callback.answer()

# ===== НАСТРОЙКИ ДЛИНЫ СООБЩЕНИЙ =====

@router.callback_query(F.data == "exceptions:length_settings")
async def length_settings_callback(callback: types.CallbackQuery):
    """Настройки минимальной длины сообщений"""
    try:
        settings = await db.get_global_settings()
        
        # Получаем минимальную длину
        if settings and hasattr(settings, 'default_min_message_length'):
            min_length = settings.default_min_message_length
        else:
            min_length = 20  # Значение по умолчанию
        
        text = (
            "📏 <b>Настройки минимальной длины сообщений</b>\n\n"
            
            "📝 <b>Что это:</b>\n"
            "Сообщения короче указанной длины (пробелы учитываются как символы) "
            "не учитываются в счетчике.\n"
            "Применяются ко ВСЕМ чатам.\n\n"
            
            f"🔢 <b>Текущая минимальная длина:</b> {min_length} символов\n\n"
            
            "⚙️ <b>Как работает:</b>\n"
            "1. Пробелы учитываются как символы\n"
            "2. Переносы строк не учитываются\n"
            "3. Если символов меньше минимальной длины - сообщение игнорируется\n"
            "4. <b>НЕ отправляется уведомление</b>\n\n"
            
            "📋 <b>Примеры:</b>\n"
            f"• 'Привет!' = 7 символов → {'игнорируется' if 7 < min_length else 'учитывается'}\n"
            f"• 'Как дела?' = 8 символов → {'игнорируется' if 8 < min_length else 'учитывается'}\n"
            f"• 'Это тестовое сообщение' = 20 символов → {'игнорируется' if 20 < min_length else 'учитывается'}\n\n"
            
            "<i>Выберите действие:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="✏️ Изменить длину",
                callback_data="exceptions:change_length"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="📊 Тестовая проверка",
                callback_data="exceptions:test_length"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить к умолчанию (20)",
                callback_data="exceptions:reset_length"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="exceptions:manage"
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

@router.callback_query(F.data == "exceptions:change_length")
async def change_length_callback(callback: types.CallbackQuery, state: FSMContext):
    """Изменение минимальной длины сообщений"""
    try:
        settings = await db.get_global_settings()
        current_length = getattr(settings, 'default_min_message_length', 20) if settings else 20
        
        text = (
            "✏️ <b>Изменение минимальной длины сообщений</b>\n\n"
            
            f"📏 <b>Текущая длина:</b> {current_length} символов\n\n"
            
            "📝 <b>Введите новое значение:</b>\n"
            "• От 5 до 100 символов\n"
            "• Рекомендуется: 15-30 символов\n\n"
            
            "⚙️ <b>Рекомендации:</b>\n"
            "• 10-15: очень низкий порог\n"
            "• 20: стандартное значение\n"
            "• 30: высокий порог качества\n"
            "• 50+: очень строгий фильтр\n\n"
            
            "❌ <b>Отмена:</b> отправьте 'отмена'"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="exceptions:length_settings"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.update_data(action_type="change_min_length")
        await state.set_state(AdminStates.waiting_for_min_length)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:test_length")
async def test_length_callback(callback: types.CallbackQuery, state: FSMContext):
    """Тестовая проверка длины сообщений"""
    try:
        settings = await db.get_global_settings()
        current_length = getattr(settings, 'default_min_message_length', 20) if settings else 20
        
        text = (
            "📊 <b>Тестовая проверка длины сообщений</b>\n\n"
            
            f"📏 <b>Текущая минимальная длина:</b> {current_length} символов\n\n"
            
            "📝 <b>Отправьте текст для проверки:</b>\n"
            "Я покажу сколько в нем символов (без пробелов) "
            f"и пройдет ли он фильтр в {current_length} символов.\n\n"
            
            "📋 <b>Примеры для теста:</b>\n"
            "• Привет, как дела?\n"
            "• Цена на товар?\n"
            "• Это длинное тестовое сообщение для проверки фильтра\n\n"
            
            "❌ <b>Отмена:</b> отправьте 'отмена'"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="exceptions:length_settings"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.update_data(action_type="test_length")
        await state.set_state(AdminStates.waiting_for_test_text)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "exceptions:reset_length")
async def reset_length_callback(callback: types.CallbackQuery):
    """Сброс минимальной длины к умолчанию (20)"""
    try:
        settings = await db.get_global_settings()
        
        if not settings:
            await callback.answer("❌ Настройки не найдены")
            return
        
        # Устанавливаем значение по умолчанию
        try:
            settings.default_min_message_length = 20
            async with db.async_session() as session:
                await session.merge(settings)
                await session.commit()
            
            await callback.answer("✅ Минимальная длина сброшена к 20 символам")
            await length_settings_callback(callback)
        except Exception as e:
            print(f"❌ Ошибка сброса длины: {e}")
            await callback.answer("❌ Ошибка сброса")
            
    except Exception as e:
        await callback.answer("❌ Ошибка сброса")
    finally:
        await callback.answer()

# ===== НАСТРОЙКИ ДЛЯ КОНКРЕТНОГО ЧАТА =====

@router.callback_query(F.data == "exceptions:chat_select")
async def chat_select_exceptions_callback(callback: types.CallbackQuery):
    """Выбор чата для управления исключениями"""
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
                
                chat_buttons.append({
                    'id': chat.id,
                    'title': display_title,
                    'icon': icon
                })
            
            text = (
                "💬 <b>Выбор чата для настроек исключений</b>\n\n"
                f"Всего групп: {len(chats)}\n\n"
                f"{chat_list}\n"
                "<i>Выберите чат:</i>"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            for chat in chat_buttons[:10]:
                display_text = f"{chat['icon']} {chat['title'][:20]}"
                if len(chat['title']) > 20:
                    display_text = display_text[:18] + ".."
                
                builder.row(
                    types.InlineKeyboardButton(
                        text=display_text,
                        callback_data=f"exceptions:chat:{chat['id']}"
                    )
                )
            
            builder.row(
                types.InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="exceptions:manage"
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
                "💬 <b>Выбор чата для исключений</b>\n\n"
                "😕 Чатов не найдено\n\n"
                "Добавьте бота в группу для управления настройками."
            )
            
            from ..keyboards.admin import get_back_to_menu_keyboard
            await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML")
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("exceptions:chat:"))
async def chat_exceptions_callback(callback: types.CallbackQuery):
    """Управление исключениями для конкретного чата"""
    try:
        chat_id = int(callback.data.split(":")[2])
        chat = await db.get_chat_by_id(chat_id)
        
        if not chat:
            await callback.answer("❌ Чат не найден")
            return
        
        # Получаем все настройки чата
        exceptions = chat.exclude_words or []
        use_regex = chat.exclude_use_regex or False
        
        # Получаем запрещенные слова для чата
        banned_words = getattr(chat, 'banned_words', [])
        
        # Получаем минимальную длину для чата
        min_length = getattr(chat, 'min_message_length', 0)
        
        exceptions_text = "\n".join([f"• {word}" for word in exceptions[:10]])
        if len(exceptions) > 10:
            exceptions_text += f"\n... и еще {len(exceptions) - 10}"
        
        banned_text = "\n".join([f"• {word}" for word in banned_words[:10]])
        if len(banned_words) > 10:
            banned_text += f"\n... и еще {len(banned_words) - 10}"
        
        if not exceptions_text:
            exceptions_text = "Нет индивидуальных исключений"
        
        if not banned_text:
            banned_text = "Нет индивидуальных запрещенных слов"
        
        text = (
            f"💬 <b>Настройки для чата '{chat.title}'</b>\n\n"
            
            "📝 <b>Исключения (не учитываются):</b>\n"
            f"{exceptions_text}\n\n"
            
            "🚫 <b>Запрещенные слова (блокировка):</b>\n"
            f"{banned_text}\n\n"
            
            f"📏 <b>Минимальная длина:</b> {min_length if min_length > 0 else 'По умолчанию'}\n"
            f"🧮 <b>Использование regex:</b> {'✅ Да' if use_regex else '❌ Нет'}\n\n"
            
            "<i>Выберите настройку для изменения:</i>"
        )
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        builder.row(
            types.InlineKeyboardButton(
                text="📝 Исключения чата",
                callback_data=f"exceptions:chat_exceptions:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🚫 Запрещенные слова",
                callback_data=f"exceptions:chat_banned:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="📏 Длина сообщений",
                callback_data=f"exceptions:chat_length:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🌐 Применить глобальные",
                callback_data=f"exceptions:chat_apply_global:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="🔄 Сбросить все настройки",
                callback_data=f"exceptions:chat_reset_all:{chat_id}"
            )
        )
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад к выбору",
                callback_data="exceptions:chat_select"
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

# ===== ОБРАБОТЧИКИ СООБЩЕНИЙ ДЛЯ НОВЫХ СОСТОЯНИЙ =====

@router.message(StateFilter(AdminStates.waiting_for_exception_word))
async def process_exception_word(message: types.Message, state: FSMContext):
    """Обработка нового слова для исключений или запрещенных слов"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
        return
    
    new_word = message.text.strip()
    
    if not new_word:
        await message.answer("❌ Слово не может быть пустым")
        return
    
    if new_word.lower() == 'отмена':
        await message.answer("❌ Добавление отменено")
        await state.clear()
        from .commands import cmd_start
        await cmd_start(message, state)
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

@router.message(StateFilter(AdminStates.waiting_for_min_length))
async def process_min_length(message: types.Message, state: FSMContext):
    """Обработка новой минимальной длины сообщений"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
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
def count_non_space_chars(text: str) -> int:
    """Считает количество символов с учетом пробелов"""
    if not text:
        return 0
    
    # Удаляем только переносы строк и табы, пробелы остаются
    import re
    clean_text = re.sub(r'[\n\t\r]+', '', text, flags=re.UNICODE)
    return len(clean_text)

@router.message(StateFilter(AdminStates.waiting_for_test_text))
async def process_test_text(message: types.Message, state: FSMContext):
    """Обработка текста для тестирования длины сообщений"""
    # Проверяем админа
    if not await check_admin_state(message.from_user.id):
        await message.answer("❌ Эта функция только для администраторов")
        await state.clear()
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
        
        # Считаем символы с пробелами (кроме переносов строк)
        char_count = count_non_space_chars(test_text)
        
        # Проверяем на запрещенные слова
        banned_words = []
        if settings and hasattr(settings, 'default_banned_words'):
            banned_words = settings.default_banned_words
        
        found_banned_words = []
        for banned_word in banned_words:
            # Ищем целые слова
            pattern = r'\b' + re.escape(banned_word.lower()) + r'\b'
            if re.search(pattern, test_text.lower()):
                found_banned_words.append(banned_word)
        
        # Формируем ответ
        text = (
            f"📊 <b>Результат проверки</b>\n\n"
            f"📝 <b>Текст:</b> {test_text[:100]}{'...' if len(test_text) > 100 else ''}\n\n"
            f"🔢 <b>Статистика:</b>\n"
            f"• Всего символов: {len(test_text)}\n"
            f"• Символов (без переносов): {char_count}\n"
            f"• Минимальная длина: {current_length}\n"
            f"• Пробелов: {test_text.count(' ')}\n\n"
        )
        
        if char_count >= current_length:
            text += f"✅ <b>Результат:</b> Сообщение пройдет фильтр ({char_count} ≥ {current_length})\n"
        else:
            text += f"❌ <b>Результат:</b> Сообщение НЕ пройдет фильтр ({char_count} < {current_length})\n"
            text += f"<i>Сообщение будет проигнорировано без уведомления</i>\n\n"
        
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

# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПРОВЕРКИ АДМИНА =====

async def check_admin_state(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором для обработки стейтов"""
    from ..utils.admin_check import is_admin
    return is_admin(user_id)