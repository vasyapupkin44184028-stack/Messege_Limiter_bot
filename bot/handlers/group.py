import random
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_ADMIN, IS_MEMBER, KICKED, LEFT
from aiogram.types import ChatMemberUpdated, ChatPermissions
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from datetime import datetime, timedelta
import asyncio
import html
import random
import re
import traceback

from ..database import db
from ..config import config
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, LEAVE_TRANSITION


router = Router()

# Глобальные переменные для хранения данных
user_empty_message_counters = {}  # Счетчики пустых сообщений: {(user_id, chat_id): count}
banned_words_cache = {}  # Кэш запрещенных слов: {chat_id: [words]}
last_messages = {}  # Сохраняем последние сообщения для автоудаления: {(chat_id, user_id): message}

# Кэш для обработки альбомов - храним ID обработанных альбомов
processed_albums = set()  # {(chat_id, media_group_id)}
album_first_messages = {}  # {(chat_id, media_group_id): message_id}


# ===== ОБРАБОТКА УДАЛЕНИЯ БОТА =====

@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_bot_left_chat(event: ChatMemberUpdated):
    """Бот покинул чат (удален или вышел сам)"""
    chat = event.chat
    chat_id = chat.id
    
    # Проверяем, что событие касается бота
    if event.new_chat_member.user.id == event.bot.id:
        print(f"🚫 Бот покинул/удален из чата: {chat.title or 'Без названия'} (ID: {chat_id})")
        
        if db.is_valid_chat_id(chat_id):
            await handle_bot_removal(chat_id, chat.title)

async def handle_bot_removal(chat_id: int, chat_title: str = None):
    """Обработка удаления бота из чата"""
    try:
        # 1. Деактивируем чат в БД
        chat_obj = await db.get_chat_by_id(chat_id)
        
        if chat_obj:
            chat_obj.is_active = False
            async with db.async_session() as session:
                await session.merge(chat_obj)
                await session.commit()
            
            print(f"✅ Чат {chat_id} деактивирован в БД")
        
        # 2. Очищаем все кэши для этого чата
        await clear_chat_caches(chat_id)
        
        # 3. Очищаем данные пользователей для этого чата (опционально)
        await clear_chat_user_data(chat_id)
        
        # 4. Логируем событие
        await db.log_action(
            "bot_left_chat",
            chat_id=chat_id,
            details=f"Чат: {chat_title or 'Неизвестно'}. Бот покинул чат."
        )
        
        print(f"✅ Все данные чата {chat_id} очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при обработке удаления бота: {e}")

async def clear_chat_caches(chat_id: int):
    """Очистка всех кэшей для чата"""
    global banned_words_cache, user_empty_message_counters, last_messages
    
    try:
        # Запрещенные слова
        if chat_id in banned_words_cache:
            del banned_words_cache[chat_id]
            print(f"   🧹 Кэш запрещенных слов для чата {chat_id} очищен")
        
        # Счетчики пустых сообщений
        keys_to_remove = [k for k in user_empty_message_counters.keys() if k[1] == chat_id]
        for key in keys_to_remove:
            del user_empty_message_counters[key]
        if keys_to_remove:
            print(f"   🧹 Удалено {len(keys_to_remove)} счетчиков пустых сообщений")
        
        # Сохраненные сообщения
        keys_to_remove = [k for k in last_messages.keys() if k[0] == chat_id]
        for key in keys_to_remove:
            del last_messages[key]
        if keys_to_remove:
            print(f"   🧹 Удалено {len(keys_to_remove)} сохраненных сообщений")
            
    except Exception as e:
        print(f"⚠️ Ошибка очистки кэшей: {e}")

async def clear_chat_user_data(chat_id: int):
    """Очистка данных пользователей чата (опционально)"""
    try:
        # Можно либо удалить данные пользователей, либо просто отметить их как неактивные
        async with db.async_session() as session:
            from sqlalchemy import select, delete
            from ..models.schemas import UserChatData
            
            # Опция 1: Удалить данные пользователей для этого чата
            result = await session.execute(
                delete(UserChatData).where(UserChatData.chat_id == chat_id)
            )
            deleted_count = result.rowcount
            
            # Опция 2: Или сбросить счетчики
            # result = await session.execute(
            #     select(UserChatData).where(UserChatData.chat_id == chat_id)
            # )
            # user_data_list = result.scalars().all()
            # for user_data in user_data_list:
            #     user_data.message_count = 0
            #     user_data.is_muted = False
            #     user_data.mute_until = None
            # deleted_count = len(user_data_list)
            
            await session.commit()
            
            if deleted_count > 0:
                print(f"   🧹 Удалено/очищено {deleted_count} записей пользователей")
                
    except Exception as e:
        print(f"⚠️ Ошибка очистки данных пользователей: {e}")

# ===== КОМАНДА ДЛЯ РУЧНОЙ ОЧИСТКИ =====

@router.message(Command("очиститьчат"))
async def cmd_clear_chat_data(message: types.Message):
    """Ручная очистка данных чата (для админов)"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        # Проверяем права
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        # Получаем подтверждение
        confirm_text = (
            "⚠️ <b>Подтверждение очистки</b>\n\n"
            "Вы уверены, что хотите очистить все данные этого чата из БД?\n\n"
            "Будут удалены:\n"
            "• Счетчики сообщений пользователей\n"
            "• Индивидуальные лимиты\n"
            "• Исключения чата\n"
            "• Уведомления\n\n"
            "Это действие необратимо!\n\n"
            "Напишите <b>ДА</b> для подтверждения"
        )
        
        confirm_msg = await message.reply(confirm_text, parse_mode="HTML")
        
        # Сохраняем для автоудаления
        await save_last_message(chat_id, user_id, confirm_msg)
        
        # Ждем подтверждение
        def check_confirm(m: types.Message):
            return m.from_user.id == user_id and m.text and m.text.upper() == "ДА"
        
        try:
            confirmation = await message.bot.wait_for(
                "message", 
                check=check_confirm, 
                timeout=30
            )
            
            # Если подтверждено, очищаем
            await clear_chat_user_data(chat_id)
            await clear_chat_caches(chat_id)
            
            await confirmation.reply("✅ Данные чата успешно очищены")
            
            # Автоудаление через 10 секунд
            await asyncio.sleep(60)
            try:
                await confirmation.delete()
            except:
                pass
            
        except asyncio.TimeoutError:
            await message.reply("❌ Время ожидания подтверждения истекло")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# Глобальные переменные для хранения данных
user_empty_message_counters = {}  # Счетчики пустых сообщений: {(user_id, chat_id): count}
banned_words_cache = {}  # Кэш запрещенных слов: {chat_id: [words]}
last_messages = {}  # Сохраняем последние сообщения для автоудаления: {(chat_id, user_id): message}

# ===== УТИЛИТЫ ДЛЯ СОХРАНЕНИЯ ПОЛЬЗОВАТЕЛЕЙ =====

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

async def ensure_user_in_chat(message: types.Message, user_id: int, chat_id: int):
    """Гарантирует, что пользователь сохранен в чате (даже если message_count = 0)"""
    try:
        # Получаем название чата из сообщения
        chat_title = message.chat.title if message.chat and hasattr(message.chat, 'title') else f"Чат {chat_id}"
        
        # Сохраняем пользователя
        user = await db.get_or_create_user(
            user_id=user_id,
            username=message.from_user.username if message.from_user else None,
            first_name=message.from_user.first_name if message.from_user else None,
            last_name=message.from_user.last_name if message.from_user else None
        )
        
        # Сохраняем чат с правильным названием
        chat = await db.get_or_create_chat(chat_id, chat_title)
        
        # Создаем запись пользователя в чате (если еще нет)
        user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
        
        return user_chat_data, chat
        
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя: {e}")
        return None, None

def get_text_from_message(message: types.Message) -> str:
    """Извлекает текст из сообщения (текст или подпись к медиа)"""
    # Проверяем основной текст
    if message.text:
        return message.text
    
    # Проверяем подпись к медиа
    if message.caption:
        return message.caption
    
    # Проверяем подпись в альбоме (может быть у первого сообщения)
    if message.caption_entities and message.caption:
        return message.caption
    
    return ""

async def get_banned_words_for_chat(chat_id: int) -> list:
    """Получает список запрещенных слов для чата"""
    # Используем кэширование для производительности
    if chat_id in banned_words_cache:
        cached_words = banned_words_cache[chat_id]
        return cached_words if isinstance(cached_words, list) else []
    
    try:
        # Получаем из БД
        banned_words = await db.get_chat_banned_words(chat_id)
        
        # Убедимся, что это список строк
        if not isinstance(banned_words, list):
            banned_words = []
        
        # Фильтруем только непустые строки
        banned_words = [word.strip() for word in banned_words if isinstance(word, str) and word.strip()]
        
        # Кэшируем
        banned_words_cache[chat_id] = banned_words
        
        print(f"   📋 Получено запрещенных слов для чата {chat_id}: {len(banned_words)}")
        if banned_words:
            print(f"   📋 Список: {banned_words[:10]}{'...' if len(banned_words) > 10 else ''}")
        
        return banned_words
        
    except Exception as e:
        print(f"⚠️ Ошибка получения запрещенных слов: {e}")
        # Возвращаем пустой список в случае ошибки
        return []
def count_non_space_chars(text: str) -> int:
    """Считает количество символов с учетом пробелов"""
    if not text:
        return 0
    
    # Удаляем только переносы строк и табы, пробелы остаются
    import re
    clean_text = re.sub(r'[\n\t\r]+', '', text, flags=re.UNICODE)
    return len(clean_text)

async def check_message_requirements(text: str, chat_id: int) -> tuple:
    """
    Проверяет сообщение на соответствие требованиям.
    Returns: (should_count, should_block, block_reason, warning)
    """
    if not text:
        return False, False, None, None
    
    print(f"   🔧 check_message_requirements: text='{text[:50]}...'")
    print(f"   📏 Длина: {len(text)} символов, без пробелов: {count_non_space_chars(text)}")
    
    # 1. СНАЧАЛА проверяем на запрещенные слова (вне зависимости от длины)
    banned_words = await get_banned_words_for_chat(chat_id)
    
    if banned_words:
        text_lower = text.lower()
        
        for banned_word in banned_words:
            if banned_word and banned_word.strip():
                # Ищем целые слова (с границами слова)
                pattern = r'\b' + re.escape(banned_word.lower().strip()) + r'\b'
                if re.search(pattern, text_lower):
                    print(f"   🚫 Обнаружено запрещенное слово: '{banned_word}'")
                    return False, True, f"banned_word_{banned_word}", f"Обнаружено запрещенное слово: {banned_word}"
    
    # 2. Если нет запрещенных слов, проверяем длину (для подсчета в лимит)
    non_space_chars = count_non_space_chars(text)
    min_length = await get_min_message_length(chat_id)
    
    print(f"   📊 Минимальная длина для учета: {min_length} символов (без пробелов)")
    
    # Сообщения короче min_length НЕ УДАЛЯЮТСЯ, просто не учитываются в лимите
    if non_space_chars < min_length:
        print(f"   ⚠️ Сообщение слишком короткое ({non_space_chars} < {min_length} символов), не учитывается в лимите")
        return False, False, "short_message", f"Сообщение слишком короткое ({non_space_chars} < {min_length} символов)"
    
    print(f"   ✅ Сообщение прошло проверки, будет учитываться в лимите")
    return True, False, None, None
    
    # 2. Только если нет запрещенных слов, проверяем длину
    non_space_chars = count_non_space_chars(text)
    min_length = await get_min_message_length(chat_id)
    
    print(f"   📊 Минимальная длина: {min_length} символов")
    
    if non_space_chars < min_length:
        print(f"   ⚠️ Сообщение слишком короткое: {non_space_chars} < {min_length}")
        return False, False, "short_message", f"Сообщение слишком короткое ({non_space_chars} < {min_length} символов)"
    
    print(f"   ✅ Сообщение прошло проверки")
    return True, False, None, None
    
    # Получаем минимальную длину из настроек
    min_length = await get_min_message_length(chat_id)
    print(f"   📊 Минимальная длина: {min_length} символов")
    
    if non_space_chars < min_length:
        print(f"   ⚠️ Сообщение слишком короткое: {non_space_chars} < {min_length}")
        return False, False, "short_message", f"Сообщение слишком короткое ({non_space_chars} меньше {min_length} символов)"
    
    print(f"   ✅ Сообщение прошло проверки")
    return True, False, None, None

async def save_last_message(chat_id: int, user_id: int, message: types.Message):
    """Сохраняет последнее сообщение для автоудаления"""
    key = (chat_id, user_id)
    last_messages[key] = message

async def delete_last_message(chat_id: int, user_id: int):
    """Удаляет сохраненное сообщение"""
    key = (chat_id, user_id)
    if key in last_messages:
        del last_messages[key]

async def handle_empty_message(message: types.Message, user_id: int, chat_id: int):
    """Обработка пустого сообщения (одиночного, не альбома) с ограничением на 3 попытки"""
    
    # Проверяем, не альбом ли это
    if message.media_group_id:
        print(f"   ⏭️ Это альбом, будет обработан в handle_media_album")
        return
    
    user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
    if user_chat_data and user_chat_data.is_muted:
        print(f"   ⏭️ Пользователь уже заблокирован, пустое сообщение игнорируется")
        try:
            await message.delete()
        except:
            pass
        return
    
    key = (user_id, chat_id)
    
    # Сохраняем пользователя в БД ДАЖЕ если он отправляет пустое сообщение
    try:
        user_chat_data, chat = await ensure_user_in_chat(message, user_id, chat_id)
        if not user_chat_data:
            print(f"⚠️ Не удалось сохранить пользователя в БД")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя в БД: {e}")
    
    # Увеличиваем счетчик пустых сообщений
    current_count = user_empty_message_counters.get(key, 0) + 1
    user_empty_message_counters[key] = current_count
    
    # Удаляем медиа СРАЗУ
    try:
        await message.delete()
        print(f"   🗑️ Пустое сообщение (одиночное) удалено сразу")
    except Exception as e:
        print(f"⚠️ Не удалось удалить пустое сообщение: {e}")    
    # Получаем уведомление из БД
    try:
        notifications = await db.get_chat_notifications(chat_id)
        warning_text = notifications.get("empty_message", 
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/стикеры/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
        
        # Добавляем счетчик если его нет в тексте
        if f"Предупреждение {current_count}/3" not in warning_text:
            warning_text += f"\n\nПредупреждение {current_count}/3"
        
        print(f"   📝 Используется уведомление из БД: {warning_text[:50]}...")
        
    except Exception as e:
        print(f"⚠️ Ошибка получения уведомления: {e}")
        # Fallback текст
        warning_text = (
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/стикеры/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
    
    try:
        # Отправляем предупреждение отдельным сообщением
        warning_msg = await message.bot.send_message(
            chat_id=chat_id,
            text=warning_text,
            parse_mode="HTML"
        )
        
        # Сохраняем предупреждение для автоудаления (только для пользователя)
        await save_last_message(chat_id, user_id, warning_msg)
        
        # Проверяем лимит (3 пустых сообщения) и мутим НЕМЕДЛЕННО
        if current_count >= 3:
            mute_until = datetime.now() + timedelta(days=3)
            
            try:
                # МУТИМ пользователя СРАЗУ
                await message.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=types.ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
                
                # Получаем уведомление о блокировке из БД (НОВЫЙ КЛЮЧ)
                try:
                    notifications = await db.get_chat_notifications(chat_id)
                    mute_text = notifications.get("empty_message_blocked",
                        "🚫 <b>Блокировка за пустые сообщения</b>\n\n"
                        "Вы отправили 3 пустых медиа-сообщения подряд без текста.\n"
                        f"Заблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                        "📞 Администратор может снять блокировку досрочно."
                    )
                    
                    # Заменяем переменную {mute_until} если есть
                    if "{mute_until}" in mute_text:
                        mute_text = mute_text.replace("{mute_until}", mute_until.strftime('%d.%m.%Y %H:%M'))
                    # Или добавляем дату если ее нет в тексте
                    elif mute_until.strftime('%d.%m.%Y %H:%M') not in mute_text:
                        mute_text += f"\n\nЗаблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}"
                    
                except Exception as e:
                    print(f"⚠️ Ошибка получения уведомления о блокировке: {e}")
                    mute_text = (
                        "🚫 <b>Блокировка за пустые сообщения</b>\n\n"
                        "Вы отправили 3 пустых медиа-сообщения подряд без текста.\n"
                        f"Заблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                        "📞 Администратор может снять блокировку досрочно."
                    )
                
                # Отправляем уведомление о муте отдельным сообщением
                mute_msg = await message.bot.send_message(
                    chat_id=chat_id,
                    text=mute_text,
                    parse_mode="HTML"
                )
                
                # Сбрасываем счетчик после мута
                user_empty_message_counters[key] = 0
                
                # Автоудаление уведомления о муте через 10 секунд
                await asyncio.sleep(60)
                try:
                    await mute_msg.delete()
                except Exception as e:
                    print(f"⚠️ Не удалось удалить уведомление о муте: {e}")
                
                # Обновляем статус в БД
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
                            user_chat_data.is_muted = True
                            user_chat_data.mute_until = mute_until
                            await session.commit()
                        else:
                            user_chat_data = UserChatData(
                                user_id=user_id,
                                chat_id=chat_id,
                                is_muted=True,
                                mute_until=mute_until,
                                message_count=0,
                                last_reset_date=datetime.utcnow()
                            )
                            session.add(user_chat_data)
                            await session.commit()
                except Exception as e:
                    print(f"⚠️ Не удалось обновить статус мута в БД: {e}")
                
                await db.log_action(
                    action_type="empty_message_mute",
                    user_id=user_id,
                    chat_id=chat_id,
                    details=f"3 пустых сообщения подряд. Мут до {mute_until}"
                )
                
                print(f"✅ Пользователь {user_id} заблокирован за 3 пустых сообщения до {mute_until}")
                
            except Exception as e:
                print(f"❌ Ошибка при муте пользователя за пустые сообщения: {e}")
                await db.log_action(
                    "mute_error",
                    user_id=user_id,
                    chat_id=chat_id,
                    details=f"Ошибка мута: {str(e)}"
                )
        
        # Удаляем предупреждение через 10 секунд
        await asyncio.sleep(60)
        try:
            await warning_msg.delete()
            await delete_last_message(chat_id, user_id)
        except Exception as e:
            print(f"⚠️ Не удалось удалить предупреждение: {e}")
    
    except Exception as e:
        print(f"❌ Общая ошибка обработки пустого сообщения: {e}")
async def check_empty_message(message: types.Message) -> bool:
    """Проверяем, является ли сообщение 'пустым'"""
    # Получаем текст или подпись
    text = get_text_from_message(message)
    
    # Проверяем, есть ли медиа
    has_media = bool(
        message.photo or 
        message.sticker or 
        message.animation or 
        message.video or 
        message.video_note or 
        message.voice or 
        message.document or 
        message.audio
    )
    
    # Если есть медиа и НЕТ текста - это пустое сообщение
    # Если есть медиа И есть текст - это НЕ пустое сообщение
    return has_media and not bool(text and text.strip())
def get_text_from_message(message: types.Message) -> str:
    """Извлекает текст из сообщения (текст или подпись к медиа)"""
    # Проверяем основной текст
    if message.text:
        return message.text
    
    # Проверяем подпись к медиа
    if message.caption:
        return message.caption
    
    # Проверяем подпись через caption_entities
    if message.caption_entities and message.caption:
        return message.caption
    
    # Для видео проверяем все возможные варианты
    if message.video:
        # Видео может иметь подпись в разных полях
        if hasattr(message, 'caption') and message.caption:
            return message.caption
    
    return ""

async def restrict_user(bot, chat_id: int, user_id: int) -> bool:
    """Блокирует пользователя в чате до 1-го числа следующего месяца"""
    try:
        now = datetime.utcnow()
        
        if now.day == 1:
            unblock_date = now.replace(day=1) + timedelta(days=32)
            unblock_date = unblock_date.replace(day=1, hour=0, minute=1, second=0)
        else:
            unblock_date = now.replace(day=1) + timedelta(days=32)
            unblock_date = unblock_date.replace(day=1, hour=0, minute=1, second=0)
        
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=types.ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            ),
            until_date=int(unblock_date.timestamp())
        )
        
        print(f"✅ Пользователь {user_id} заблокирован до {unblock_date.strftime('%d.%m.%Y %H:%M')}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка блокировки пользователя {user_id}: {e}")
        return False

async def block_for_swear_word(bot, chat_id: int, user_id: int, word: str):
    """Блокирует пользователя за запрещенное слово"""
    mute_until = datetime.now() + timedelta(days=3)
    
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=mute_until
        )
        
        block_text = (
            f"🚫 Блокировка за запрещенное слово\n\n"
            f"Обнаружено запрещенное слово: {word}\n"
            f"Вы заблокированы до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
            "📞 Администратор может снять блокировку досрочно."
        )
        
        return block_text, mute_until
        
    except Exception as e:
        print(f"❌ Ошибка блокировки за запрещенное слово: {e}")
        return None, None

async def handle_swear_word_block(message: types.Message, user_id: int, chat_id: int, block_reason: str):
    """Обработка блокировки за маты с маскировкой"""
    banned_word = block_reason.replace("banned_word_", "") if block_reason and block_reason.startswith("banned_word_") else "неизвестное"
    
    # Получаем текст сообщения и маскируем его
    original_text = get_text_from_message(message)
    banned_words_list = await get_banned_words_for_chat(chat_id)
    
    # Проверяем что banned_words_list является списком
    if not isinstance(banned_words_list, list):
        banned_words_list = []
    
    masked_text, found_words = mask_swear_words(original_text, banned_words_list)
    
    block_text, mute_until = await block_for_swear_word(message.bot, chat_id, user_id, banned_word)
    
    if block_text and mute_until:
        # Удаляем сообщение СРАЗУ
        try:
            await message.delete()
        except:
            pass
        
        # Формируем уведомление с маскировкой
        notification_text = (
            f"🚫 <b>Блокировка за запрещенное слово</b>\n\n"
            f"Обнаружено запрещенное слово: <code>{'*' * len(banned_word)}</code>\n"
        )
        
        if masked_text and masked_text.strip():
            notification_text += f"\n📝 <b>Сообщение (с маскировкой):</b>\n<code>{html.escape(masked_text[:200])}</code>"
        
        notification_text += f"\n\nВы заблокированы до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n"
        notification_text += "📞 Администратор может снять блокировку досрочно."
        
        # Отправляем уведомление
        block_msg = await message.bot.send_message(
            chat_id, 
            text=notification_text,
            parse_mode="HTML"
        )
        
        # Сохраняем для автоудаления
        await save_last_message(chat_id, user_id, block_msg)
        
        # Обновляем статус в БД
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
                    user_chat_data.is_muted = True
                    user_chat_data.mute_until = mute_until
                    await session.commit()
                else:
                    user_chat_data = UserChatData(
                        user_id=user_id,
                        chat_id=chat_id,
                        is_muted=True,
                        mute_until=mute_until,
                        message_count=0,
                        last_reset_date=datetime.utcnow()
                    )
                    session.add(user_chat_data)
                    await session.commit()
        except Exception as e:
            print(f"⚠️ Не удалось обновить статус мута в БД: {e}")
        
        # Автоудаление через 60 секунд
        await asyncio.sleep(60)
        try:
            await block_msg.delete()
            await delete_last_message(chat_id, user_id)
        except:
            pass

async def handle_short_message(message: types.Message, chat_id: int, user_id: int, warning: str):
    """Обработка короткого сообщения - БЕЗ отправки уведомления"""
    # Просто игнорируем короткое сообщение, не отправляем уведомление
    print(f"   ⚠️ Короткое сообщение от {user_id}: {warning}")
    # Удаляем сообщение пользователя (опционально, можно закомментировать)
    try:
        await message.delete()
    except:
        pass

async def count_and_check_limit(message: types.Message, user_id: int, chat_id: int, text: str):
    """Подсчет сообщений и проверка лимита"""
    try:
        # Проверяем, не заблокирован ли пользователь
        user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
        if user_chat_data and user_chat_data.is_muted:
            # Пользователь заблокирован - отправляем соответствующее уведомление
            
            # Проверяем тип блокировки
            if user_chat_data.mute_until:
                # Блокировка с датой окончания (за маты или пустые сообщения)
                # Определяем причину блокировки по mute_until
                try:
                    # Проверяем, это блокировка за маты или пустые
                    # Просто отправляем общее уведомление
                    notifications = await db.get_chat_notifications(chat_id)
                    blocked_text = notifications.get("user_blocked",
                        "🚫 <b>Вы заблокированы</b>\n\n"
                        "Вы исчерпали лимит сообщений.\n"
                        "Доступ восстановится 1-го числа следующего месяца.\n\n"
                        "📞 Для покупки дополнительных сообщений: {contact_link}"
                    )
                    
                    # Получаем контактную ссылку
                    settings = await db.get_global_settings()
                    contact_link = settings.contact_link if settings else ""
                    
                    # Заменяем переменные
                    formatted_text = blocked_text.replace("{contact_link}", contact_link)
                    
                except Exception as e:
                    formatted_text = "🚫 Вы заблокированы. Ожидайте разблокировки."
            else:
                # Блокировка за лимит (без даты окончания - до 1-го числа)
                try:
                    notifications = await db.get_chat_notifications(chat_id)
                    blocked_text = notifications.get("limit_exceeded",
                        "🚫 <b>Лимит сообщений исчерпан</b>\n\n"
                        "Вы использовали все {user_limit} сообщений в этом месяце.\n"
                        "Доступ восстановится 1-го числа следующего месяца.\n\n"
                        "📞 Для покупки дополнительных сообщений: {contact_link}"
                    )
                    
                    # Получаем лимит пользователя
                    user_limit = await db.get_user_limit(user_id, chat_id)
                    
                    # Получаем контактную ссылку
                    settings = await db.get_global_settings()
                    contact_link = settings.contact_link if settings else ""
                    
                    # Заменяем переменные
                    formatted_text = blocked_text.replace("{user_limit}", str(user_limit))
                    formatted_text = formatted_text.replace("{contact_link}", contact_link)
                    
                except Exception as e:
                    formatted_text = "🚫 Лимит сообщений исчерпан. Ожидайте 1-го числа."
            
            # Отправляем уведомление
            blocked_msg = await message.reply(formatted_text, parse_mode="HTML")
            
            # Автоудаление через 5 секунд
            await asyncio.sleep(5)
            try:
                await blocked_msg.delete()
            except:
                pass
            
            print(f"   ⏭️ Пользователь заблокирован, сообщение не учитывается")
            return
        
        # Сбрасываем счетчик пустых сообщений для хороших сообщений
        key = (user_id, chat_id)
        if key in user_empty_message_counters:
            user_empty_message_counters[key] = 0
            print(f"   🔄 Сброшен счетчик пустых сообщений для пользователя {user_id}")
        
        # Учитываем сообщение
        message_count = await db.update_message_count(user_id, chat_id)
        print(f"   📊 Сообщение #{message_count}")
        
        # Получаем лимит для пользователя
        user_limit = await db.get_user_limit(user_id, chat_id)
        
        # Проверяем предупреждения
        if user_limit is not None and message_count == 3:
            user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
            if not user_chat_data or not user_chat_data.is_muted:
                remaining = user_limit - message_count
                
                # Получаем уведомления из БД
                notifications = await db.get_chat_notifications(chat_id)
                warning_text = notifications.get("warning_3_messages", 
                    "⚠️ <b>Внимание!</b>\n\n"
                    "У вас осталось {N} бесплатных сообщений в этом месяце."
                ).replace("{N}", str(remaining))
                
                warning_msg = await message.reply(warning_text, parse_mode="HTML")
                print(f"   ⚠️ Отправлено предупреждение")
                
                # Сохраняем для автоудаления
                await save_last_message(chat_id, user_id, warning_msg)
                
                # Автоудаление через 15 секунд
                await asyncio.sleep(15)
                try:
                    await warning_msg.delete()
                    await delete_last_message(chat_id, user_id)
                except:
                    pass
                
                await db.log_action("warning_sent", user_id=user_id, chat_id=chat_id, 
                                  details=f"Осталось сообщений: {remaining}")
        
        # Проверяем превышение лимита
        if user_limit is not None and message_count >= user_limit:
            print(f"   🚫 Превышен лимит! {message_count}/{user_limit}")
            
            user_data = await db.get_or_create_user_chat_data(user_id, chat_id)
            if user_data and user_data.is_muted:
                print(f"   ⏭️ Пользователь уже заблокирован, повторная блокировка не требуется")
                return
            
            # Блокируем пользователя
            success = await restrict_user(message.bot, chat_id, user_id)
            if success:
                # Обновляем статус в БД
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
                        user_chat_data.is_muted = True
                        user_chat_data.mute_until = datetime.utcnow()
                        await session.commit()
                
                # Отправляем уведомление о лимите
                notifications = await db.get_chat_notifications(chat_id)
                blocked_text = notifications.get("limit_exceeded",
                    "🚫 <b>Лимит сообщений исчерпан</b>\n\n"
                    "Вы использовали все {user_limit} сообщений в этом месяце.\n"
                    "Доступ восстановится 1-го числа следующего месяца.\n\n"
                    "📞 Для покупки дополнительных сообщений: {contact_link}"
                )
                
                # Получаем контактную ссылку
                settings = await db.get_global_settings()
                contact_link = settings.contact_link if settings else ""
                
                # Заменяем переменные
                formatted_text = blocked_text.replace("{user_limit}", str(user_limit))
                formatted_text = formatted_text.replace("{contact_link}", contact_link)
                
                blocked_msg = await message.reply(formatted_text, parse_mode="HTML")
                print(f"   🔒 Пользователь заблокирован за лимит")
                
                # Сохраняем для автоудаления
                await save_last_message(chat_id, user_id, blocked_msg)
                
                # Автоудаление через 15 секунд
                await asyncio.sleep(15)
                try:
                    await blocked_msg.delete()
                    await delete_last_message(chat_id, user_id)
                except:
                    pass
                
                # Логируем блокировку
                await db.log_action("user_blocked", user_id=user_id, chat_id=chat_id, 
                                  details=f"Лимит: {user_limit}, Сообщений: {message_count}")
            else:
                print(f"   ❌ Не удалось заблокировать пользователя")
                await db.log_action("block_failed", user_id=user_id, chat_id=chat_id, 
                                  details="Ошибка блокировки пользователя")
                
    except Exception as e:
        print(f"   ❌ Ошибка обработки сообщения: {e}")
        await db.log_action("message_error", user_id=user_id, chat_id=chat_id, 
                          details=f"Ошибка: {str(e)}")
# ===== КОМАНДЫ ДЛЯ ГРУПП =====

@router.message(Command("start"))
async def cmd_start_in_group(message: types.Message):
    """Команда /start в группе - не работает"""
    return

@router.message(Command("help"))
async def cmd_help_in_group(message: types.Message):
    """Команда /help в группе - показываем только групповую справку"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    text = (
        "❓ Помощь по боту в этой группе\n\n"
        "📝 Как я работаю:\n"
        "• Считаю сообщения каждого участника\n"
        "• Ограничиваю 5 сообщениями в месяц (по умолчанию)\n"
        "• Удаляю 'пустые' сообщения (медиа без текста)\n"
        "• Блокирую при превышении лимита\n"
        "• Разблокирую 1-го числа\n\n"
        "📏 Новые правила:\n"
        "• Сообщения короче 20 символов (без пробелов) не учитываются\n"
        "• Запрещенные слова ведут к блокировке на 3 дня\n"
        "• Пустые медиа-сообщения ограничены 3 попытками\n\n"
        "👤 Ваши команды:\n"
        "• /мойстатус - ваш текущий статус\n"
        "• /ботстатус - статус бота в этой группе\n"
        "• /правила - правила чата\n\n"
        "👮 Для администраторов:\n"
        "Настройки в личных сообщениях с ботом"
    )
    
    await message.reply(text, parse_mode="HTML")
    await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
    
    # Автоудаление через 15 секунд
    await asyncio.sleep(15)
    try:
        await message.delete()
        await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
    except:
        pass

@router.message(Command("id"))
async def cmd_id_in_group(message: types.Message):
    """Команда /id в группе - показывает ID группы"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    chat_id = message.chat.id
    
    text = (
        f"💬 Информация о чате\n"
        f"ID группы: {chat_id}\n"
        f"Название: {message.chat.title or 'Без названия'}\n"
        f"Тип: {message.chat.type}"
    )
    
    if message.from_user:
        text += f"\n\n👤 Ваш ID: {message.from_user.id}"
    
    await message.reply(text, parse_mode="HTML")
    await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
    
    # Автоудаление через 15 секунд
    await asyncio.sleep(15)
    try:
        await message.delete()
        await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
    except:
        pass

@router.message(Command("правила"))
@router.message(Command("rules"))
async def cmd_rules_in_group(message: types.Message):
    """Правила чата"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    text = (
        "📜 Правила чата\n\n"
        
        "1. Лимит сообщений:\n"
        "   • 5 сообщений в месяц (по умолчанию)\n"
        "   • Лимит сбрасывается 1-го числа\n\n"
        
        "2. Качество сообщений:\n"
        "   • Минимум 20 символов (без пробелов)\n"
        "   • Медиа без описания считаются 'пустыми'\n"
        "   • Максимум 3 пустых сообщения\n\n"
        
        "3. Запрещено:\n"
        "   • Матерные и оскорбительные слова\n"
        "   • Спам и флуд\n"
        "   • Реклама без согласования\n\n"
        
        "4. Наказания:\n"
        "   • Запрещенные слова → блокировка 3 дня\n"
        "   • 3 пустых сообщения → блокировка 3 дня\n"
        "   • Превышение лимита → блокировка до 1-го числа\n\n"
        
        "📞 По вопросам обращайтесь к администраторам"
    )
    
    await message.reply(text, parse_mode="HTML")
    await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
    
    # Автоудаление через 15 секунд
    await asyncio.sleep(15)
    try:
        await message.delete()
        await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
    except:
        pass

@router.message(F.text == "/ботстатус")
async def bot_status_in_group(message: types.Message):
    """Показывает статус бота в группе"""
    try:
        member = await message.bot.get_chat_member(
            chat_id=message.chat.id,
            user_id=message.bot.id
        )
        
        chat = await db.get_chat_by_id(message.chat.id)
        is_active = chat.is_active if chat else True
        
        status_text = (
            f"🤖 Статус бота в этой группе\n\n"
            f"• Статус: {member.status}\n"
            f"• ID группы: {message.chat.id}\n"
            f"• Активен: {'✅ Да' if is_active else '❌ Нет'}\n"
        )
        
        if member.status in ["administrator", "creator"]:
            status_text += (
                f"\n✅ Бот администратор!\n"
                f"• Удаление сообщений: {'✅' if member.can_delete_messages else '❌'}\n"
                f"• Блокировка: {'✅' if member.can_restrict_members else '❌'}\n"
                f"• Закрепление: {'✅' if member.can_pin_messages else '❌'}\n"
            )
            
            if is_active:
                status_text += f"\n⚙️ Бот готов к работе!\nСообщения учитываются автоматически."
            else:
                status_text += f"\n⏸️ Бот отключен в этом чате\nВключите его через админ-панель."
        else:
            status_text += "\n⚠️ Бот не администратор!\nДобавьте права для работы."
        
        await message.reply(status_text, parse_mode="HTML")
        await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await message.delete()
            await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(F.text == "/мойстатус")
async def my_status_in_group(message: types.Message):
    """Показывает статус пользователя в группе и удаляет через 10 секунд"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        # Проверяем, является ли пользователь администратором
        try:
            member = await message.bot.get_chat_member(chat_id, user_id)
            if member.status in ["administrator", "creator"]:
                reply_msg = await message.reply(
                    "👑 Вы администратор этого чата!\n\n"
                    "Ваши сообщения не учитываются в лимите.\n"
                    "Вы можете управлять настройками бота через личные сообщения.",
                    parse_mode="HTML"
                )
                
                # Удаляем оба сообщения через 10 секунд
                await asyncio.sleep(60)
                try:
                    await reply_msg.delete()
                except:
                    pass
                try:
                    await message.delete()
                except:
                    pass
                return
        except:
            pass
        
        # Получаем данные из БД
        user_data = await db.get_or_create_user_chat_data(user_id, chat_id)
        
        # Получаем лимит для пользователя
        user_limit = await db.get_user_limit(user_id, chat_id)
        
        # Проверяем счетчик пустых сообщений
        empty_count = user_empty_message_counters.get((user_id, chat_id), 0)
        
        if not user_data:
            status_text = (
                f"👤 Ваш статус\n\n"
                f"• Сообщений: 0\n"
                f"• Лимит: {user_limit}\n"
                f"• Пустых сообщений: {empty_count}/3\n"
                f"• Статус: 🟢 Активен\n\n"
                f"Отправьте сообщение, чтобы начать учет."
            )
        else:
            status = "🔴 Заблокирован" if user_data.is_muted else "🟢 Активен"
            
            status_text = (
                f"👤 Ваш статус\n\n"
                f"• Сообщений: {user_data.message_count}\n"
                f"• Лимит: {user_limit}\n"
                f"• Осталось: {max(0, user_limit - user_data.message_count)}\n"
                f"• Пустых сообщений: {empty_count}/3\n"
                f"• Статус: {status}\n"
            )
            
            if user_data.is_muted:
                status_text += "\n⚠️ Вы заблокированы за превышение лимита\n"
                
                settings = await db.get_global_settings()
                auto_unblock_days = settings.auto_unblock_days if settings else 30
                
                if user_data.mute_until:
                    unblock_date = user_data.mute_until + timedelta(days=auto_unblock_days)
                    days_left = (unblock_date - datetime.utcnow()).days
                    if days_left > 0:
                        status_text += f"Автоматическая разблокировка через: {days_left} дней\n"
                
                if settings and settings.contact_link:
                    status_text += f"Контакт для покупки: {settings.contact_link}"
                else:
                    status_text += "Обратитесь к администратору для разблокировки."
        
        # Отправляем ответ
        reply_msg = await message.reply(status_text, parse_mode="HTML")
        
        # Удаляем оба сообщения через 10 секунд
        await asyncio.sleep(60)
        try:
            await reply_msg.delete()
        except:
            pass
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        # В случае ошибки тоже отправляем и удаляем
        reply_msg = await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")
        
        await asyncio.sleep(60)
        try:
            await reply_msg.delete()
        except:
            pass
        try:
            await message.delete()
        except:
            pass
# ===== СОБЫТИЯ ГРУППЫ =====

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    """Обрабатывает ВСЕ сообщения в группах"""
    
    print(f"📨 [ГРУППА] Чат: {message.chat.id}, Пользователь: {message.from_user.id if message.from_user else 'N/A'}")
    
    # 1. Проверка from_user
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # 2. Проверка типа чата
    if not db.is_valid_chat_id(chat_id):
        print(f"   ⏭️ Пропускаем личный диалог")
        return
    
    # 3. Проверка админа пользователя
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            print(f"   👑 Администратор - пропускаем")
            return
    except Exception as e:
        print(f"   ⚠️ Ошибка проверки прав: {e}")
    
    # 4. Проверяем медиа-альбомы
    if message.media_group_id:
        print(f"   📷 Медиа-альбом обнаружен")
        await handle_media_album(message, user_id, chat_id)
        return
    
    # 5. Если это не альбом, продолжаем обычную обработку
    try:
        user_chat_data, chat = await ensure_user_in_chat(message, user_id, chat_id)
        
        if not user_chat_data or not chat:
            print(f"   ⚠️ Не удалось сохранить пользователя/чат в БД")
            return
            
        print(f"   💾 Чат сохранен: {chat.title}")
        
        # 6. ПРОВЕРЯЕМ - если пользователь уже заблокирован, прекращаем обработку
        if user_chat_data.is_muted:
            print(f"   ⏭️ Пользователь уже заблокирован, прекращаем обработку")
            return
        
    except Exception as e:
        print(f"   ❌ Ошибка БД: {e}")
        return
    
    # 7. Проверяем, активен ли бот в этом чате
    if not chat.is_active:
        print(f"   ⏸️ Бот неактивен в этом чате")
        return
    
    # 8. Получаем текст сообщения (основной или подпись)
    text = get_text_from_message(message)
    
    # 9. Проверяем "пустые" сообщения (медиа без текста)
    # Только одиночные медиа (не альбомы)
    has_media = bool(
        message.photo or 
        message.sticker or 
        message.animation or 
        message.video or
        message.video_note or
        message.voice or
        message.document or
        message.audio
    )
    
    if has_media and not message.media_group_id:  
        text = get_text_from_message(message)
        if not (text and text.strip()):
            print(f"   🗑️ Одиночное медиа (видео/фото) без текста - УДАЛЯЕМ")
            await handle_empty_message(message, user_id, chat_id)
            return
    
    # 10. Проверяем требования к тексту
    if text and text.strip():
        should_count, should_block, block_reason, warning = await check_message_requirements(text, chat_id)
        
        if should_block:
            # ЗАПРЕЩЕННОЕ СЛОВО - БЛОКИРУЕМ ВНЕ ЗАВИСИМОСТИ ОТ ДЛИНЫ
            print(f"   🚫 Запрещенное слово: {block_reason} - БЛОКИРОВКА")
            try:
                await handle_swear_word_block(message, user_id, chat_id, block_reason)
            except Exception as e:
                print(f"❌ Ошибка обработки запрещенного слова: {e}")
                try:
                    await message.delete()
                except:
                    pass
            return
            
        elif should_count:
            # Сообщение прошло все проверки, будет учитываться в лимите
            print(f"   📊 Сообщение учитывается в лимите")
            await count_and_check_limit(message, user_id, chat_id, text)
            
            # Проверяем исключения
            if await check_exceptions(message, chat_id):
                print(f"   📝 Сообщение-исключение - сбросим счетчик")
                # Сбрасываем счетчик сообщений для исключений
                await db.reset_message_count_for_user(user_id, chat_id)
        else:
            # Сообщение слишком короткое (НЕ запрещенное) - НЕ УДАЛЯЕМ, просто не учитываем
            print(f"   ⚠️ Короткое сообщение: {warning} - НЕ УДАЛЯЕМ, не считаем в лимите")
            # Ничего не делаем - сообщение остается в чате
            return
    
    # 11. Сообщения без текста (не медиа) - игнорируем
    elif not text and not has_media:
        print(f"   ⏭️ Сообщение без текста и медиа - игнорируем")
        return
    
    # 12. Подсчет сообщений и проверка лимита
    await count_and_check_limit(message, user_id, chat_id, text if text and text.strip() else "")

# ===== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ =====

@router.message(Command("статистика"))
@router.message(Command("stats"))
async def cmd_stats_in_group(message: types.Message):
    """Статистика чата"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    try:
        chat_id = message.chat.id
        
        async with db.async_session() as session:
            from sqlalchemy import select, func
            from ..models.schemas import UserChatData, Chat
            
            result = await session.execute(
                select(func.sum(UserChatData.message_count))
                .where(UserChatData.chat_id == chat_id)
            )
            total_messages = result.scalar() or 0
            
            result = await session.execute(
                select(func.count(UserChatData.user_id.distinct()))
                .where(UserChatData.chat_id == chat_id)
            )
            total_users = result.scalar() or 0
            
            result = await session.execute(
                select(func.count(UserChatData.id))
                .where(UserChatData.chat_id == chat_id)
                .where(UserChatData.is_muted == True)
            )
            blocked_users = result.scalar() or 0
        
        empty_counters = len([k for k in user_empty_message_counters.keys() if k[1] == chat_id])
        
        text = (
            f"📊 Статистика чата\n\n"
            f"💬 Сообщений всего: {total_messages}\n"
            f"👥 Пользователей: {total_users}\n"
            f"🚫 Заблокировано: {blocked_users}\n"
            f"🗑️ Активных счетчиков пустых сообщений: {empty_counters}\n\n"
            f"<i>Статистика обновляется в реальном времени</i>"
        )
        
        await message.reply(text, parse_mode="HTML")
        await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await message.delete()
            await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения статистики: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("сброситьсчетчик"))
@router.message(Command("resetcounter"))
async def cmd_reset_counter_in_group(message: types.Message):
    """Сброс счетчика пустых сообщений (только для администраторов)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        keys_to_remove = [k for k in user_empty_message_counters.keys() if k[1] == chat_id]
        for key in keys_to_remove:
            del user_empty_message_counters[key]
        
        count = len(keys_to_remove)
        await message.reply(f"✅ Сброшено счетчиков пустых сообщений: {count}")
        await save_last_message(message.chat.id, message.from_user.id if message.from_user else 0, message)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await message.delete()
            await delete_last_message(message.chat.id, message.from_user.id if message.from_user else 0)
        except:
            pass
        
        await db.log_action(
            "reset_empty_counters",
            user_id=user_id,
            chat_id=chat_id,
            details=f"Сброшено {count} счетчиков"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("сброситьпустые"))
async def cmd_reset_empty_user(message: types.Message):
    """Сброс счетчика пустых сообщений для конкретного пользователя (админы)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        args = message.text.split()
        if len(args) < 2:
            reply_msg = await message.reply(
                "❌ Неверный формат команды\n"
                "Использование: /сброситьпустые <user_id>\n"
                "Пример: /сброситьпустые 123456789"
            )
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target = args[1]
        
        if not target.isdigit():
            reply_msg = await message.reply("❌ User ID должен быть числом")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target_user_id = int(target)
        
        key = (target_user_id, chat_id)
        if key in user_empty_message_counters:
            old_count = user_empty_message_counters[key]
            del user_empty_message_counters[key]
            reply_msg = await message.reply(f"✅ Счетчик пустых сообщений для пользователя {target_user_id} сброшен\n"
                               f"Было предупреждений: {old_count}")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            
            await db.log_action(
                "reset_user_empty_counter",
                user_id=user_id,
                chat_id=chat_id,
                details=f"Админ сбросил счетчик пустых сообщений для пользователя {target_user_id}"
            )
        else:
            reply_msg = await message.reply(f"ℹ️ У пользователя {target_user_id} нет активных предупреждений о пустых сообщениях")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("разблокировать"))
async def cmd_unblock_user(message: types.Message):
    """Разблокировка пользователя (админы)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Получаем название чата
    chat_title = message.chat.title if message.chat and hasattr(message.chat, 'title') else f"Чат {chat_id}"
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        args = message.text.split()
        if len(args) < 2:
            reply_msg = await message.reply(
                "❌ Неверный формат команды\n"
                "Использование: /разблокировать <user_id>\n"
                "Пример: /разблокировать 123456789"
            )
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target = args[1]
        
        if not target.isdigit():
            reply_msg = await message.reply("❌ User ID должен быть числом")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target_user_id = int(target)
        
        try:
            await message.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
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
            
            # ОБНОВЛЯЕМ название чата при разблокировке
            await db.get_or_create_chat(chat_id, chat_title)
            
            async with db.async_session() as session:
                from sqlalchemy import select
                from ..models.schemas import UserChatData
                
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == target_user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
                
                if user_chat_data:
                    user_chat_data.is_muted = False
                    user_chat_data.mute_until = None
                    user_chat_data.message_count = 0
                    await session.commit()
            
            reply_msg = await message.reply(f"✅ Пользователь {target_user_id} разблокирован")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            
            await db.log_action(
                "manual_unblock",
                user_id=user_id,
                chat_id=chat_id,
                details=f"Админ разблокировал пользователя {target_user_id}"
            )
            
        except Exception as e:
            reply_msg = await message.reply(f"❌ Ошибка разблокировки: {html.escape(str(e))}")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("поиск"))
async def cmd_search_user(message: types.Message):
    """Поиск пользователя по ID в списке пользователей чата (админы)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        args = message.text.split()
        if len(args) < 2:
            reply_msg = await message.reply(
                "🔍 Поиск пользователя по ID\n\n"
                "Использование: /поиск <user_id>\n"
                "Пример: /поиск 123456789\n\n"
                "Бот покажет информацию о пользователе в этом чате."
            )
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target = args[1]
        
        if not target.isdigit():
            reply_msg = await message.reply("❌ User ID должен быть числом")
            await save_last_message(chat_id, user_id, reply_msg)
            
            # Автоудаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await reply_msg.delete()
                await delete_last_message(chat_id, user_id)
            except:
                pass
            return
        
        target_user_id = int(target)
        
        # Получаем информацию о пользователе из БД
        async with db.async_session() as session:
            from sqlalchemy import select
            from ..models.schemas import User, UserChatData
            
            result = await session.execute(
                select(User, UserChatData)
                .join(UserChatData, User.id == UserChatData.user_id)
                .where(User.id == target_user_id)
                .where(UserChatData.chat_id == chat_id)
            )
            user_data = result.first()
            
            if user_data:
                user, user_chat_data = user_data
                
                # Получаем информацию из Telegram API
                try:
                    tg_member = await message.bot.get_chat_member(chat_id, target_user_id)
                    status = tg_member.status
                except:
                    status = "Неизвестно"
                
                username = f"@{user.username}" if user.username else "Нет username"
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                
                # Проверяем счетчик пустых сообщений
                empty_count = user_empty_message_counters.get((target_user_id, chat_id), 0)
                
                text = (
                    f"🔍 Результаты поиска\n\n"
                    f"👤 Пользователь ID: {target_user_id}\n"
                    f"📝 Имя: {full_name or 'Не указано'}\n"
                    f"👤 Username: {username}\n"
                    f"💬 Статус в чате: {status}\n\n"
                    f"📊 Статистика в этом чате:\n"
                    f"• Сообщений: {user_chat_data.message_count}\n"
                    f"• Пустых сообщений: {empty_count}/3\n"
                    f"• Заблокирован: {'✅ Да' if user_chat_data.is_muted else '❌ Нет'}\n"
                    f"• Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n\n"
                    f"<i>Пользователь найден в базе данных бота</i>"
                )
            else:
                text = (
                    f"🔍 Результаты поиска\n\n"
                    f"Пользователь ID {target_user_id} не найден в базе данных этого чата.\n\n"
                    f"<i>Пользователь может еще не отправлять сообщения в этом чате.</i>"
                )
        
        reply_msg = await message.reply(text, parse_mode="HTML")
        await save_last_message(chat_id, user_id, reply_msg)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await reply_msg.delete()
            await delete_last_message(chat_id, user_id)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка поиска: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("восстановитьназвания"))
async def cmd_restore_titles(message: types.Message):
    """Восстановить названия чатов в базе данных (админы)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_title = message.chat.title if hasattr(message.chat, 'title') else f"Чат {chat_id}"
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        # Обновляем название текущего чата
        success = await db.update_chat_title(chat_id, chat_title)
        
        if success:
            reply_msg = await message.reply(
                f"✅ Название чата обновлено в базе данных\n"
                f"Новое название: {chat_title}"
            )
        else:
            reply_msg = await message.reply(
                f"❌ Не удалось обновить название чата\n"
                f"Проверьте логи бота"
            )
        
        await save_last_message(chat_id, user_id, reply_msg)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await reply_msg.delete()
            await delete_last_message(chat_id, user_id)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("восстановитьназвание"))
async def cmd_restore_chat_title(message: types.Message):
    """Восстановить название чата в базе данных (админы)"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_title = message.chat.title if message.chat and hasattr(message.chat, 'title') else f"Чат {chat_id}"
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Эта команда только для администраторов")
            return
        
        # Обновляем название текущего чата
        chat = await db.get_or_create_chat(chat_id, chat_title)
        
        if chat:
            reply_msg = await message.reply(
                f"✅ Название чата обновлено в базе данных\n"
                f"Новое название: {chat_title}"
            )
        else:
            reply_msg = await message.reply(
                f"❌ Не удалось обновить название чата\n"
                f"Проверьте логи бота"
            )
        
        await save_last_message(chat_id, user_id, reply_msg)
        
        # Автоудаление через 15 секунд
        await asyncio.sleep(15)
        try:
            await reply_msg.delete()
            await delete_last_message(chat_id, user_id)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {html.escape(str(e))}", parse_mode="HTML")

@router.message(Command("активировать"))
@router.message(Command("activate"))
async def cmd_activate_bot(message: types.Message):
    """Ручная активация бота в чате (для админов)"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        # Проверяем права
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ Только администраторы могут активировать бота")
            return
        
        # Проверяем права бота
        bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply("❌ Сначала сделайте бота администратором!")
            return
        
        # Активируем чат в БД
        chat = await db.get_or_create_chat(chat_id, message.chat.title)
        if chat:
            chat.is_active = True
            async with db.async_session() as session:
                await session.merge(chat)
                await session.commit()
            
            await message.reply(
                "✅ Бот активирован в этом чате!\n\n"
                "Теперь я буду:\n"
                "• Считать сообщения\n"
                "• Удалять пустые медиа\n"
                "• Блокировать за маты\n"
                "• Ограничивать 5 сообщениями/месяц\n\n"
                "⚙️ Настройки: /start в ЛС с ботом"
            )
            
            await db.log_action("manual_activation", user_id=user_id, chat_id=chat_id, 
                              details=f"Админ активировал бота вручную")
        else:
            await message.reply("❌ Ошибка активации")
            
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("статусбота"))
@router.message(Command("botstatus"))
async def cmd_bot_status(message: types.Message):
    """Проверка статуса бота в чате"""
    try:
        chat_id = message.chat.id
        
        # Проверяем права бота
        bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
        
        # Проверяем в БД
        chat = await db.get_chat_by_id(chat_id)
        
        status_text = f"🤖 Статус бота в этом чате:\n\n"
        status_text += f"• Права бота: {bot_member.status}\n"
        status_text += f"• Активен в БД: {'✅ Да' if chat and chat.is_active else '❌ Нет'}\n"
        
        if bot_member.status in ["administrator", "creator"]:
            status_text += f"• Удаление сообщений: {'✅' if bot_member.can_delete_messages else '❌'}\n"
            status_text += f"• Блокировка: {'✅' if bot_member.can_restrict_members else '❌'}\n"
        
        if chat and chat.is_active:
            status_text += "\n✅ Бот активен и готов к работе!"
        else:
            status_text += "\n⚠️ Бот не активен. Используйте /активировать"
        
        await message.reply(status_text)
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("тестфильтров"))
async def cmd_test_filters(message: types.Message):
    """Тест фильтров (только для админов)"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем права
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            return
        
        test_texts = [
            ("коротко", False, True, "Должно быть коротким"),
            ("нормальное сообщение длиннее 20 символов", True, False, "Должно пройти"),
            ("сообщение с хуй", True, True, "Должно заблокировать за мат"),
            ("просто пизда какое-то", True, True, "Должно заблокировать за мат"),
        ]
        
        results = []
        for text, should_count, should_block, description in test_texts:
            count_result, block_result, reason, warning = await check_message_requirements(text, chat_id)
            
            status = "✅" if (count_result == should_count and block_result == should_block) else "❌"
            results.append(f"{status} {description}: счет={count_result}, блок={block_result}")
        
        await message.reply("🧪 Результаты теста:\n\n" + "\n".join(results))
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("статусчата"))
async def cmd_chat_status(message: types.Message):
    """Проверка статуса чата в БД"""
    try:
        chat_id = message.chat.id
        
        if not db.is_valid_chat_id(chat_id):
            await message.reply("❌ Это не валидный ID группового чата")
            return
        
        chat = await db.get_chat_by_id(chat_id)
        
        if chat:
            # Кэш статус
            global banned_words_cache, user_empty_message_counters, last_messages
            
            banned_cache_count = 1 if chat_id in banned_words_cache else 0
            empty_counters_count = len([k for k in user_empty_message_counters.keys() if k[1] == chat_id])
            saved_messages_count = len([k for k in last_messages.keys() if k[0] == chat_id])
            
            text = (
                f"📊 <b>Статус чата в БД</b>\n\n"
                f"💬 Чат: {chat.title or 'Без названия'}\n"
                f"🆔 ID: {chat_id}\n"
                f"🟢 Активен: {'✅ Да' if chat.is_active else '❌ Нет'}\n"
                f"📊 Лимит: {chat.message_limit} сообщ./мес.\n"
                f"📏 Минимальная длина: {chat.min_message_length if hasattr(chat, 'min_message_length') else 'Не задано'}\n\n"
                f"🧹 <b>Кэш в памяти:</b>\n"
                f"• Запрещенные слова: {banned_cache_count}\n"
                f"• Счетчики пустых сообщений: {empty_counters_count}\n"
                f"• Сохраненные сообщения: {saved_messages_count}\n\n"
                f"🕒 Создан: {chat.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"🔄 Обновлен: {chat.updated_at.strftime('%d.%m.%Y %H:%M') if chat.updated_at else 'Никогда'}"
            )
        else:
            text = (
                f"📊 <b>Статус чата в БД</b>\n\n"
                f"💬 Чат ID: {chat_id}\n\n"
                f"❌ <b>Чат не найден в базе данных</b>\n\n"
                f"Возможные причины:\n"
                f"1. Бот не активирован в этом чате\n"
                f"2. Бот был удален из чата\n"
                f"3. Проблемы с подключением к БД\n\n"
                f"Используйте /активировать для добавления чата"
            )
        
        await message.reply(text, parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
async def cleanup_chat_on_removal(chat_id: int):
    """Очистка всех кэшей при удалении бота из чата"""
    global banned_words_cache, user_empty_message_counters, last_messages
    
    # Очистка кэша запрещенных слов
    if chat_id in banned_words_cache:
        del banned_words_cache[chat_id]
    
    # Очистка счетчиков пустых сообщений
    keys_to_remove = [k for k in user_empty_message_counters.keys() if k[1] == chat_id]
    for key in keys_to_remove:
        del user_empty_message_counters[key]
    
    # Очистка сохраненных сообщений
    keys_to_remove = [k for k in last_messages.keys() if k[0] == chat_id]
    for key in keys_to_remove:
        del last_messages[key]
    
    print(f"🧹 Очищены кэши для чата {chat_id}")

@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_bot_left_chat(event: ChatMemberUpdated):
    """Бот покинул чат"""
    if event.new_chat_member.user.id == event.bot.id:
        print(f"🚫 Бот удален из чата: {event.chat.title} (ID: {event.chat.id})")
        
        # Деактивируем чат в БД
        chat = await db.get_chat_by_id(event.chat.id)
        if chat:
            chat.is_active = False
            async with db.async_session() as session:
                await session.merge(chat)
                await session.commit()
        
        # Очищаем кэши
        await cleanup_chat_on_removal(event.chat.id)
@router.message(Command("статусчата"))
async def cmd_chat_status(message: types.Message):
    """Проверка статуса чата"""
    try:
        chat_id = message.chat.id
        
        # Проверяем, является ли это групповым чатом
        if message.chat.type not in ["group", "supergroup"]:
            await message.reply("❌ Эта команда работает только в группах/супергруппах")
            return
        
        # Проверяем наличие бота в чате
        try:
            bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
            bot_in_chat = bot_member.status not in ["kicked", "left"]
            bot_status = bot_member.status
        except Exception as e:
            bot_in_chat = False
            bot_status = f"Ошибка: {e}"
        
        # Проверяем в БД
        chat = await db.get_chat_by_id(chat_id)
        
        if chat:
            db_status = "✅ Найден в БД"
            is_active = "🟢 Активен" if chat.is_active else "🔴 Неактивен"
        else:
            db_status = "❌ Не найден в БД"
            is_active = "❌ Нет данных"
        
        text = (
            f"📊 <b>Статус чата</b>\n\n"
            f"💬 Чат: {message.chat.title or 'Без названия'}\n"
            f"🆔 ID: {chat_id}\n"
            f"👥 Тип: {message.chat.type}\n\n"
            f"🤖 <b>Статус бота:</b>\n"
            f"• В чате: {'✅ Да' if bot_in_chat else '❌ Нет'}\n"
            f"• Статус: {bot_status}\n\n"
            f"🗄️ <b>База данных:</b>\n"
            f"• {db_status}\n"
            f"• Статус: {is_active}\n\n"
        )
        
        if not bot_in_chat:
            text += (
                f"⚠️ <b>Бота нет в этом чате!</b>\n\n"
                f"Чтобы активировать бота:\n"
                f"1. Добавьте бота в чат\n"
                f"2. Сделайте администратором\n"
                f"3. Используйте /активировать\n"
            )
        elif chat and not chat.is_active:
            text += (
                f"ℹ️ <b>Бот не активен в этом чате</b>\n\n"
                f"Используйте команду /активировать\n"
                f"для включения функций бота"
            )
        
        # Автоудаление сообщения через 15 секунд
        reply_msg = await message.reply(text, parse_mode="HTML")
        await save_last_message(chat_id, message.from_user.id if message.from_user else 0, reply_msg)
        
        await asyncio.sleep(15)
        try:
            await reply_msg.delete()
            await delete_last_message(chat_id, message.from_user.id if message.from_user else 0)
        except:
            pass
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("тестмедиа"))
async def test_media(message: types.Message):
    """Тестовая команда для проверки медиа-обработки"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    text = get_text_from_message(message)
    
    response = (
        f"🔍 Тест медиа-обработки\n\n"
        f"📊 Параметры сообщения:\n"
        f"• Текст: {message.text or 'нет'}\n"
        f"• Подпись: {message.caption or 'нет'}\n"
        f"• Фото: {'есть' if message.photo else 'нет'}\n"
        f"• Видео: {'есть' if message.video else 'нет'}\n"
        f"• Альбом ID: {message.media_group_id or 'нет'}\n"
        f"• Тип контента: {message.content_type}\n\n"
        f"📝 Извлеченный текст: '{text}'\n"
        f"🔢 Длина текста: {len(text) if text else 0}\n"
        f"🧹 Пустое сообщение? {await check_empty_message(message)}"
    )
    
    await message.reply(response, parse_mode="HTML")


async def cleanup_old_albums():
    """Очистка старых записей альбомов из кэша (старше 5 минут)"""
    global processed_albums, album_first_messages
    
    current_time = datetime.now()
    max_age = timedelta(minutes=5)
    
    # Очищаем processed_albums
    albums_to_remove = set()
    for album_key in list(processed_albums):
        chat_id, media_group_id = album_key
        # Можно использовать время как критерий очистки
        albums_to_remove.add(album_key)
    
    # Оставляем только последние 100 записей
    if len(processed_albums) > 100:
        processed_albums = set(list(processed_albums)[-100:])
    
    # Очищаем album_first_messages
    keys_to_remove = []
    for key in list(album_first_messages.keys()):
        # Удаляем старые записи или если обработаны
        keys_to_remove.append(key)
    
    # Оставляем только последние 100 записей
    if len(album_first_messages) > 100:
        items = list(album_first_messages.items())
        album_first_messages = dict(items[-100:])
    
    print(f"   🧹 Очищен кэш альбомов, осталось: {len(processed_albums)} альбомов, {len(album_first_messages)} первых сообщений")
    
    print(f"   🧹 Очищен кэш альбомов, осталось: {len(processed_albums)}")

@router.message(Command("статус_альбомов"))
async def cmd_album_status(message: types.Message):
    """Показать статус кэша альбомов"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            return
    except:
        return
    
    status = (
        f"📊 Статус кэша альбомов\n\n"
        f"• Обработанных альбомов: {len(processed_albums)}\n"
        f"• Сохраненных первых сообщений: {len(album_first_messages)}\n"
        f"• Счетчиков пустых сообщений: {len(user_empty_message_counters)}\n"
        f"• Сохраненных сообщений: {len(last_messages)}\n\n"
        f"💡 Кэш очищается автоматически при превышении 1000 записей"
    )
    
    await message.reply(status, parse_mode="HTML")
    await save_last_message(chat_id, user_id, message)

def mask_swear_words(text: str, banned_words: list) -> tuple:
    """
    Маскирует запрещенные слова в тексте и возвращает (маскированный_текст, найденные_слова)
    """
    if not text or not banned_words:
        return text, []  # ВАЖНО: возвращаем кортеж (text, []), а не text
    
    text_lower = text.lower()
    found_words = []
    masked_text = text
    
    for banned_word in banned_words:
        if not banned_word or not isinstance(banned_word, str):
            continue
            
        banned_word_lower = banned_word.lower().strip()
        if not banned_word_lower:
            continue
            
        if banned_word_lower in text_lower:
            found_words.append(banned_word)
            # Создаем маску из звездочек
            mask = '*' * len(banned_word)
            # Заменяем слово на маску (сохраняя регистр)
            masked_text = re.sub(
                re.escape(banned_word), 
                mask, 
                masked_text, 
                flags=re.IGNORECASE
            )
    
    return masked_text, found_words  # ВАЖНО: возвращаем кортеж
async def cleanup_old_albums():
    """Очистка старых записей альбомов из кэша"""
    global processed_albums, album_first_messages
    
    # Оставляем только свежие записи (последние 100)
    if len(processed_albums) > 100:
        albums_list = list(processed_albums)
        processed_albums = set(albums_list[-100:])
    
    if len(album_first_messages) > 100:
        # Удаляем старые записи
        items = list(album_first_messages.items())
        album_first_messages = dict(items[-100:])
    
    print(f"   🧹 Очищен кэш альбомов, осталось: {len(processed_albums)}")

async def handle_empty_message_for_album(message: types.Message, user_id: int, chat_id: int, album_size: int = 1):
    """Обработка пустого альбома (без текста) - только для альбомов без текста"""
    print(f"   📊 Обработка пустого альбома, size={album_size}")
    
    user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
    if user_chat_data and user_chat_data.is_muted:
        print(f"   ⏭️ Пользователь уже заблокирован, пустой альбом игнорируется")
        return
    
    key = (user_id, chat_id)
    
    # Увеличиваем счетчик пустых сообщений
    # За альбом считается как за ОДНО пустое сообщение
    current_count = user_empty_message_counters.get(key, 0) + 1
    user_empty_message_counters[key] = current_count
    
    # Получаем уведомление из БД
    try:
        notifications = await db.get_chat_notifications(chat_id)
        warning_text = notifications.get("empty_message", 
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/стикеры/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
        
        # Добавляем счетчик если его нет в тексте
        if f"Предупреждение {current_count}/3" not in warning_text:
            warning_text += f"\n\nПредупреждение {current_count}/3"
        
        print(f"   📝 Используется уведомление из БД: {warning_text[:50]}...")
        
    except Exception as e:
        print(f"⚠️ Ошибка получения уведомления: {e}")
        # Fallback текст
        warning_text = (
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/стикеры/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
    
    try:
        # Отправляем предупреждение отдельным сообщением
        warning_msg = await message.bot.send_message(
            chat_id=chat_id,
            text=warning_text,
            parse_mode="HTML"
        )
        
        # Сохраняем предупреждение для автоудаления (только для пользователя)
        await save_last_message(chat_id, user_id, warning_msg)
        
        # Проверяем лимит (3 пустых сообщения) и мутим НЕМЕДЛЕННО
        if current_count >= 3:
            mute_until = datetime.now() + timedelta(days=3)
            
            try:
                # МУТИМ пользователя СРАЗУ
                await message.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=types.ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
                
                # Получаем уведомление о блокировке из БД (НОВЫЙ КЛЮЧ)
                try:
                    notifications = await db.get_chat_notifications(chat_id)
                    mute_text = notifications.get("empty_message_blocked",
                        "🚫 <b>Блокировка за пустые сообщения</b>\n\n"
                        "Вы отправили 3 пустых медиа-сообщения подряд без текста.\n"
                        f"Заблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                        "📞 Администратор может снять блокировку досрочно."
                    )
                    
                    # Заменяем переменную {mute_until} если есть
                    if "{mute_until}" in mute_text:
                        mute_text = mute_text.replace("{mute_until}", mute_until.strftime('%d.%m.%Y %H:%M'))
                    # Или добавляем дату если ее нет в тексте
                    elif mute_until.strftime('%d.%m.%Y %H:%M') not in mute_text:
                        mute_text += f"\n\nЗаблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}"
                    
                except Exception as e:
                    print(f"⚠️ Ошибка получения уведомления о блокировке: {e}")
                    mute_text = (
                        "🚫 <b>Блокировка за пустые сообщения</b>\n\n"
                        "Вы отправили 3 пустых медиа-сообщения подряд без текста.\n"
                        f"Заблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                        "📞 Администратор может снять блокировку досрочно."
                    )
                
                # Отправляем уведомление о муте отдельным сообщением
                mute_msg = await message.bot.send_message(
                    chat_id=chat_id,
                    text=mute_text,
                    parse_mode="HTML"
                )
                
                # Сбрасываем счетчик после мута
                user_empty_message_counters[key] = 0
                
                # Автоудаление уведомления о муте через 60 секунд
                await asyncio.sleep(60)
                try:
                    await mute_msg.delete()
                except Exception as e:
                    print(f"⚠️ Не удалось удалить уведомление о муте: {e}")
                
                # Обновляем статус в БД
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
                            user_chat_data.is_muted = True
                            user_chat_data.mute_until = mute_until
                            await session.commit()
                        else:
                            user_chat_data = UserChatData(
                                user_id=user_id,
                                chat_id=chat_id,
                                is_muted=True,
                                mute_until=mute_until,
                                message_count=0,
                                last_reset_date=datetime.utcnow()
                            )
                            session.add(user_chat_data)
                            await session.commit()
                except Exception as e:
                    print(f"⚠️ Не удалось обновить статус мута в БД: {e}")
                
                await db.log_action(
                    action_type="empty_message_mute",
                    user_id=user_id,
                    chat_id=chat_id,
                    details=f"3 пустых сообщения подряд. Мут до {mute_until}"
                )
                
                print(f"✅ Пользователь {user_id} заблокирован за 3 пустых сообщения до {mute_until}")
                
            except Exception as e:
                print(f"❌ Ошибка при муте пользователя за пустые сообщения: {e}")
                await db.log_action(
                    "mute_error",
                    user_id=user_id,
                    chat_id=chat_id,
                    details=f"Ошибка мута: {str(e)}"
                )
        
        # Удаляем предупреждение через 60 секунд
        await asyncio.sleep(60)
        try:
            await warning_msg.delete()
            await delete_last_message(chat_id, user_id)
        except Exception as e:
            print(f"⚠️ Не удалось удалить предупреждение: {e}")
    
    except Exception as e:
        print(f"❌ Общая ошибка обработки пустого альбома: {e}")
async def check_exceptions(message: types.Message, chat_id: int) -> bool:
    """Проверяем, попадает ли сообщение под исключения"""
    text = get_text_from_message(message)
    
    if not text:
        return False
    
    try:
        exceptions = await db.get_chat_exceptions(chat_id)
        if exceptions is None:
            exceptions = []
    except Exception as e:
        print(f"⚠️ Ошибка получения исключений: {e}")
        exceptions = config.DEFAULT_EXCLUDE_WORDS
    
    text_lower = text.lower()
    for word in exceptions:
        if word and word.lower() in text_lower:
            return True
    
    return False

# ===== ОБРАБОТКА АЛЬБОМОВ =====


async def handle_media_album_subsequent(message: types.Message, user_id: int, chat_id: int):
    """Обработка последующих сообщений альбома"""
    media_group_id = message.media_group_id
    album_key = (chat_id, media_group_id)
    
    # Проверяем информацию об альбоме
    if album_key in album_first_messages:
        # Увеличиваем счетчик размера альбома
        album_first_messages[album_key]['album_size'] += 1
        
        print(f"   📸 Последующее сообщение альбома {media_group_id}, размер={album_first_messages[album_key]['album_size']}")
        
        # Если альбом без текста и помечен на удаление - удаляем это сообщение
        if album_first_messages[album_key].get('deleted', False):
            try:
                await message.delete()
                album_first_messages[album_key]['deleted_messages'].append(message.message_id)
                print(f"   🗑️ Удалено сообщение пустого альбома")
                
                # Проверяем, все ли сообщения альбома удалены
                if len(album_first_messages[album_key]['deleted_messages']) >= album_first_messages[album_key]['album_size']:
                    # Все сообщения альбома удалены, отправляем одно предупреждение
                    await handle_empty_album_warning(message, user_id, chat_id, album_first_messages[album_key]['album_size'])
                    
            except Exception as e:
                print(f"⚠️ Не удалось удалить сообщение альбома: {e}")
        # Если альбом с текстом - НИЧЕГО НЕ ДЕЛАЕМ

# Глобальные переменные для обработки альбомов
active_albums = {}  # {album_key: {"messages": [], "has_text": bool, "text": str, "timer": task, "user_id": int, "chat_id": int}}
MAX_ALBUM_SIZE = 10  # Максимальный размер альбома (по спецификации Telegram)

async def handle_media_album(message: types.Message, user_id: int, chat_id: int):
    """Обработка медиа-альбомов с таймером ожидания"""
    media_group_id = message.media_group_id
    album_key = (chat_id, media_group_id)
    
    text = get_text_from_message(message)
    has_text = bool(text and text.strip())
    
    print(f"📸 Альбом сообщение: album_key={album_key}, has_text={has_text}, text={text[:50] if text else ''}")
    
    if album_key not in active_albums:
        # Новый альбом
        active_albums[album_key] = {
            "messages": [message],
            "has_text": has_text,
            "text": text or "",
            "user_id": user_id,
            "chat_id": chat_id,
            "start_time": datetime.now(),
            "processed": False
        }
        
        print(f"   🆕 Новый альбом, сообщений: 1, текст: {'есть' if has_text else 'нет'}")
        
        # Запускаем таймер на обработку альбома
        asyncio.create_task(process_album_after_delay(album_key))
    else:
        # Добавляем сообщение в существующий альбом
        active_albums[album_key]["messages"].append(message)
        
        # Обновляем информацию о тексте (берем из первого сообщения)
        if not active_albums[album_key]["has_text"] and has_text:
            active_albums[album_key]["has_text"] = has_text
            active_albums[album_key]["text"] = text
        
        print(f"   ➕ Добавлено в альбом, всего сообщений: {len(active_albums[album_key]['messages'])}")

async def process_album_after_delay(album_key, delay_seconds=1.5):
    """Обработка альбома после задержки (ждем все сообщения)"""
    await asyncio.sleep(delay_seconds)
    
    if album_key not in active_albums:
        print(f"   ⏭️ Альбом уже обработан или удален")
        return
    
    album_data = active_albums[album_key]
    
    if album_data.get("processed", False):
        print(f"   ⏭️ Альбом уже обработан")
        return
    
    album_data["processed"] = True
    
    messages = album_data["messages"]
    has_text = album_data["has_text"]
    text = album_data["text"]
    user_id = album_data["user_id"]
    chat_id = album_data["chat_id"]
    
    print(f"   🔄 Обработка альбома {album_key}: {len(messages)} сообщений, текст: {'есть' if has_text else 'нет'}")
    
    if not has_text:
        # Альбом без текста - удаляем все сообщения
        print(f"   🗑️ Альбом без текста, удаляем все сообщения")
        deleted_count = 0
        
        for msg in messages:
            try:
                await msg.delete()
                deleted_count += 1
            except Exception as e:
                print(f"   ⚠️ Не удалось удалить сообщение: {e}")
        
        if deleted_count > 0:
            # Отправляем одно предупреждение за весь альбом
            await handle_empty_album_warning(messages[0], user_id, chat_id, deleted_count)
    else:
        # Альбом с текстом - проверяем требования
        print(f"   📝 Альбом с текстом, проверяем требования")
        
        # Используем первый message для проверки
        first_message = messages[0]
        
        should_count, should_block, block_reason, warning = await check_message_requirements(text, chat_id)
        
        if should_block:
            print(f"   🚫 Запрещенное слово в альбоме: {block_reason}")
            # Обрабатываем как мат
            await handle_swear_word_block(first_message, user_id, chat_id, block_reason)
        elif should_count:
            # Альбом проходит проверку, учитываем его
            print(f"   📊 Альбом с допустимым текстом, учитываем")
            await count_and_check_limit(first_message, user_id, chat_id, text)
        else:
            # Альбом с коротким текстом - НЕ удаляем, просто игнорируем
            print(f"   ⚠️ Альбом с коротким текстом: {warning}")
    
    # Очищаем альбом из активных
    if album_key in active_albums:
        del active_albums[album_key]
        print(f"   🧹 Альбом удален из активных")

async def handle_empty_album_warning(message: types.Message, user_id: int, chat_id: int, album_size: int):
    """Отправка одного предупреждения за весь альбом без текста"""
    print(f"   ⚠️ Отправка предупреждения за пустой альбом ({album_size} сообщений)")
    
    user_chat_data = await db.get_or_create_user_chat_data(user_id, chat_id)
    if user_chat_data and user_chat_data.is_muted:
        print(f"   ⏭️ Пользователь уже заблокирован, пустой альбом игнорируется")
        return
    
    key = (user_id, chat_id)
    
    # Увеличиваем счетчик пустых сообщений
    # За альбом считается как за ОДНО пустое сообщение (независимо от количества медиа)
    current_count = user_empty_message_counters.get(key, 0) + 1
    user_empty_message_counters[key] = current_count
    
    # Получаем уведомление из БД
    try:
        notifications = await db.get_chat_notifications(chat_id)
        warning_text = notifications.get("empty_message", 
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
        
        # Добавляем счетчик если его нет в тексте
        if f"Предупреждение {current_count}/3" not in warning_text:
            warning_text += f"\n\nПредупреждение {current_count}/3"
        
    except Exception as e:
        print(f"⚠️ Ошибка получения уведомления: {e}")
        warning_text = (
            "⚠️ <b>Внимание!</b>\n"
            "Просто картинки/видео без текста нельзя отправлять в чат.\n"
            "Оформите объявление текстом или добавьте описание к медиа.\n\n"
            f"Предупреждение {current_count}/3"
        )
    
    try:
        # Отправляем предупреждение отдельным сообщением
        warning_msg = await message.bot.send_message(
            chat_id=chat_id,
            text=warning_text,
            parse_mode="HTML"
        )
        
        # Сохраняем предупреждение для автоудаления
        await save_last_message(chat_id, user_id, warning_msg)
        
        # Проверяем лимит (3 пустых сообщения) и мутим НЕМЕДЛЕННО
        if current_count >= 3:
            mute_until = datetime.now() + timedelta(days=3)
            
            try:
                # МУТИМ пользователя СРАЗУ
                await message.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=types.ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
                
                # Отправляем уведомление о блокировке
                mute_text = (
                    "🚫 <b>Блокировка за пустые сообщения</b>\n\n"
                    "Вы отправили 3 пустых медиа-сообщения подряд без текста.\n"
                    f"Заблокирован до: {mute_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                    "📞 Администратор может снять блокировку досрочно."
                )
                
                mute_msg = await message.bot.send_message(
                    chat_id=chat_id,
                    text=mute_text,
                    parse_mode="HTML"
                )
                
                # Сбрасываем счетчик после мута
                user_empty_message_counters[key] = 0
                
                # Автоудаление уведомления о муте через 60 секунд
                await asyncio.sleep(60)
                try:
                    await mute_msg.delete()
                except Exception as e:
                    print(f"⚠️ Не удалось удалить уведомление о муте: {e}")
                
                # Обновляем статус в БД
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
                            user_chat_data.is_muted = True
                            user_chat_data.mute_until = mute_until
                            await session.commit()
                except Exception as e:
                    print(f"⚠️ Не удалось обновить статус мута в БД: {e}")
                
                print(f"✅ Пользователь {user_id} заблокирован за 3 пустых сообщения до {mute_until}")
                
            except Exception as e:
                print(f"❌ Ошибка при муте пользователя за пустые сообщения: {e}")
        
        # Удаляем предупреждение через 60 секунд
        await asyncio.sleep(60)
        try:
            await warning_msg.delete()
            await delete_last_message(chat_id, user_id)
        except Exception as e:
            print(f"⚠️ Не удалось удалить предупреждение: {e}")
    
    except Exception as e:
        print(f"❌ Ошибка отправки предупреждения: {e}")
@router.message(Command("тестпроверки"))
async def cmd_test_check(message: types.Message):
    """Тест проверки сообщений"""
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        # Проверяем права
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            return
    except:
        return
    
    test_messages = [
        "как ты",  # 7 символов - не считается
        "как ты считаешь",  # 15 символов - не считается  
        "как ты считаешь что лучше будет",  # 28 символов - считается
        "хуй",  # запрещенное слово - блокировка
        "привет, это тест",  # 16 символов - не считается
        "это очень длинное сообщение для проверки подсчета символов"  # >20 символов - считается
    ]
    
    results = []
    min_length = await get_min_message_length(chat_id)
    banned_words = await get_banned_words_for_chat(chat_id)
    
    for test_text in test_messages:
        should_count, should_block, block_reason, warning = await check_message_requirements(test_text, chat_id)
        
        status = []
        if should_block:
            status.append("🚫 Блокировка (мат)")
        elif should_count:
            status.append("✅ Учитывается")
        else:
            if "short_message" in str(block_reason):
                status.append("⚠️ Короткое (не считается)")
            else:
                status.append("❌ Не учитывается")
        
        char_count = count_non_space_chars(test_text)
        results.append(f"{test_text[:30]}... | {char_count} симв. | {' | '.join(status)}")
    
    response = (
        f"🧪 <b>Тест проверки сообщений</b>\n\n"
        f"📏 Минимальная длина: {min_length} символов (без пробелов)\n"
        f"🚫 Запрещенные слова: {len(banned_words)}\n\n"
        f"<b>Результаты:</b>\n" + "\n".join(results)
    )
    
    await message.reply(response, parse_mode="HTML")
    await save_last_message(chat_id, user_id, message)