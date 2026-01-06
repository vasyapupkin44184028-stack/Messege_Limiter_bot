import types
from aiogram import Router
from click import Command
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, text, func, update, Table, MetaData
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
import json
import re

from .models.schemas import Base, Chat, User, UserChatData, GlobalSettings, ActionLog, Statistics
from .config import config

class Database:
    async def search_chats(self, search_text: str) -> list:
        """Поиск чатов по названию или ID"""
        if not self.async_session:
            return []

        try:
            async with self.async_session() as session:
                from sqlalchemy import select, or_
            
                if search_text.startswith('-') and search_text[1:].isdigit():
                    # Поиск по ID чата
                    chat_id = int(search_text)
                    result = await session.execute(
                        select(Chat)
                        .where(Chat.id == chat_id)
                    )
                else:
                    # Поиск по названию
                    search_pattern = f"%{search_text}%"
                    result = await session.execute(
                        select(Chat)
                        .where(Chat.title.ilike(search_pattern))
                        .order_by(Chat.title)
                        .limit(20)
                    )
            
                chats = result.scalars().all()
            
                # Фильтруем только валидные чаты
                valid_chats = []
                for chat in chats:
                    if self.is_valid_chat_id(chat.id):
                        valid_chats.append(chat)
            
                return valid_chats
            
        except Exception as e:
            print(f"⚠️ Ошибка поиска чатов: {e}")
            return []

    async def search_users_in_chat(self, chat_id: int, search_text: str) -> list:
        """Поиск пользователей в чате по имени, username или ID"""
        if not self.is_valid_chat_id(chat_id) or not self.async_session:
            return []
    
        try:
            async with self.async_session() as session:
                from sqlalchemy import select, or_, and_

                # Специальный поиск по звездочке (*) - все пользователи
                if search_text.strip() == "*":
                    result = await session.execute(
                        select(UserChatData, User)
                        .join(User, UserChatData.user_id == User.id)
                        .where(UserChatData.chat_id == chat_id)
                        .order_by(UserChatData.message_count.desc())
                        .limit(50)
                    )
                elif search_text.isdigit():
                    # Поиск по ID пользователя
                    user_id = int(search_text)
                    result = await session.execute(
                        select(UserChatData, User)
                        .join(User, UserChatData.user_id == User.id)
                        .where(
                            and_(
                                UserChatData.chat_id == chat_id,
                                UserChatData.user_id == user_id
                            )
                        )
                    )
                else:
                    # Поиск по имени, фамилии или username (без учета регистра)
                    search_pattern = f"%{search_text.strip()}%"
                    result = await session.execute(
                        select(UserChatData, User)
                        .join(User, UserChatData.user_id == User.id)
                        .where(
                            and_(
                                UserChatData.chat_id == chat_id,
                                or_(
                                    User.first_name.ilike(search_pattern),
                                    User.last_name.ilike(search_pattern),
                                    User.username.ilike(search_pattern)
                                )
                            )
                        )
                        .order_by(User.first_name)
                        .limit(20)
                    )
        
                return result.all()
        
        except Exception as e:
            print(f"⚠️ Ошибка поиска пользователей: {e}")
            return []
    def __init__(self):
        try:
            self.engine = create_async_engine(config.DB_URL, echo=False)
            self.async_session = async_sessionmaker(
                self.engine, 
                class_=AsyncSession,
                expire_on_commit=False
            )
            print(f"✅ База данных подключена: {config.DB_URL}")
        except Exception as e:
            print(f"⚠️ Ошибка подключения к БД: {e}")
            print("⚠️ Бот будет работать без сохранения данных")
            self.engine = None
            self.async_session = None
    
    async def create_tables(self):
        """Создание таблиц в БД"""
        if not self.engine:
            return
            
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("✅ Таблицы БД созданы/проверены")
            
            # Проверяем и добавляем недостающие колонки
            await self.check_and_add_columns()
        except Exception as e:
            print(f"⚠️ Ошибка создания таблиц: {e}")
    
    def is_valid_chat_id(self, chat_id: int) -> bool:
        """Проверяем, является ли ID валидным для сохранения в БД"""
        if chat_id > 0:
            return False
        
        chat_id_str = str(chat_id)
        if len(chat_id_str) == 10 and chat_id_str.startswith('-5'):
            return False
        
        if len(chat_id_str) == 11 and chat_id_str.startswith('-1'):
            return False
        
        return chat_id < -99
    
    async def check_and_add_columns(self):
        """Проверяем и добавляем недостающие колонки во всех таблицах"""
        if not self.engine:
            return
    
        try:
            async with self.engine.begin() as conn:
                # Создаем метаданные и отражаем структуру БД
                metadata = MetaData()
                await conn.run_sync(metadata.reflect)
        
                # ===== ТАБЛИЦА chats =====
                if 'chats' in metadata.tables:
                    table = metadata.tables['chats']
                    existing_columns = {c.name for c in table.columns}
            
                    # Список необходимых колонок для chats
                    required_columns = {
                        'id', 'title', 'message_limit', 'exclude_words', 
                        'exclude_use_regex', 'banned_words', 'notification_texts', 
                        'custom_notifications', 'is_active', 'created_at', 'updated_at'
                    }
            
                    missing_columns = required_columns - existing_columns
            
                    if missing_columns:
                        print(f"⚠️ Найдены недостающие колонки в chats: {missing_columns}")
                
                        for column_name in missing_columns:
                            if column_name == 'exclude_use_regex':
                                await conn.execute(
                                    text(f"ALTER TABLE chats ADD COLUMN {column_name} BOOLEAN DEFAULT 0")
                                )
                            elif column_name == 'banned_words':
                                await conn.execute(
                                    text(f"ALTER TABLE chats ADD COLUMN {column_name} JSON DEFAULT NULL")
                                )
                            elif column_name == 'custom_notifications':
                                await conn.execute(
                                    text(f"ALTER TABLE chats ADD COLUMN {column_name} JSON DEFAULT '{{}}'")
                                )
                            else:
                                print(f"   ⚠️ Неизвестный тип колонки: {column_name}")
                                continue
                            print(f"✅ Добавлена колонка в chats: {column_name}")
        
                # ===== ТАБЛИЦА user_chat_data =====
                if 'user_chat_data' in metadata.tables:
                    table = metadata.tables['user_chat_data']
                    existing_columns = {c.name for c in table.columns}
            
                    required_columns = {
                        'id', 'user_id', 'chat_id', 'message_count', 'custom_limit',
                        'custom_limit_expires_at',  # НОВАЯ КОЛОНКА
                        'is_muted', 'mute_until', 'last_reset_date', 'last_custom_reset_date',
                        'is_custom_limit_active', 'created_at', 'updated_at'
                    }

                    missing_columns = required_columns - existing_columns
            
                    if missing_columns:
                        print(f"⚠️ Найдены недостающие колонки в user_chat_data: {missing_columns}")
                
                        for column_name in missing_columns:
                            if column_name == 'last_custom_reset_date':
                                await conn.execute(
                                    text(f"ALTER TABLE user_chat_data ADD COLUMN {column_name} DATETIME")
                                )
                            elif column_name == 'custom_limit_expires_at':
                                await conn.execute(
                                    text(f"ALTER TABLE user_chat_data ADD COLUMN {column_name} DATETIME")
                                )
                            elif column_name == 'is_custom_limit_active':
                                await conn.execute(
                                    text(f"ALTER TABLE user_chat_data ADD COLUMN {column_name} BOOLEAN DEFAULT 0")
                                )
                            else:
                                print(f"   ⚠️ Неизвестный тип колонки: {column_name}")
                                continue
                            print(f"✅ Добавлена колонка в user_chat_data: {column_name}")
        
                # ===== ТАБЛИЦА global_settings =====
                if 'global_settings' in metadata.tables:
                    table = metadata.tables['global_settings']
                    existing_columns = {c.name for c in table.columns}
            
                    required_columns = {
                        'id', 'contact_link', 'default_message_limit', 
                        'default_exclude_words', 'default_exclude_use_regex',
                        'default_notifications', 'default_banned_words',
                        'auto_unblock_days', 'security_log_enabled', 'default_min_message_length', 'updated_at'
                    }

                    missing_columns = required_columns - existing_columns
            
                    if missing_columns:
                        print(f"⚠️ Найдены недостающие колонки в global_settings: {missing_columns}")
                
                        for column_name in missing_columns:
                            if column_name == 'default_exclude_use_regex':
                                await conn.execute(
                                    text(f"ALTER TABLE global_settings ADD COLUMN {column_name} BOOLEAN DEFAULT 0")
                                )
                            elif column_name == 'default_banned_words':
                                await conn.execute(
                                    text(f"ALTER TABLE global_settings ADD COLUMN {column_name} JSON DEFAULT '[]'")
                                )
                            else:
                                print(f"   ⚠️ Неизвестный тип колонки: {column_name}")
                                continue
                            print(f"✅ Добавлена колонка в global_settings: {column_name}")
        
                # ===== ТАБЛИЦА users =====
                if 'users' in metadata.tables:
                    table = metadata.tables['users']
                    existing_columns = {c.name for c in table.columns}
            
                    required_columns = {
                        'id', 'username', 'first_name', 'last_name', 
                        'is_global_admin', 'created_at'
                    }
            
                    missing_columns = required_columns - existing_columns
            
                    if missing_columns:
                        print(f"⚠️ Найдены недостающие колонки в users: {missing_columns}")
                
                        for column_name in missing_columns:
                            if column_name == 'is_global_admin':
                                await conn.execute(
                                    text(f"ALTER TABLE users ADD COLUMN {column_name} BOOLEAN DEFAULT 0")
                                )
                            else:
                                print(f"   ⚠️ Неизвестный тип колонки: {column_name}")
                                continue
                            print(f"✅ Добавлена колонка в users: {column_name}")
        
                print("✅ Структура всех таблиц проверена и обновлена")
                        
        except Exception as e:
            print(f"⚠️ Ошибка при проверке структуры таблицы: {e}")
    async def get_or_create_chat(self, chat_id: int, chat_title: str = None) -> Chat:
        """Получить или создать чат в БД (с обновлением названия)"""
        if not self.is_valid_chat_id(chat_id):
            return None
    
        if not self.async_session:
            return Chat(id=chat_id, title=chat_title or f"Чат {chat_id}")
        
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
                if not chat:
                    # Получаем глобальные настройки для исключений
                    settings = await self.get_global_settings()
                    default_exceptions = (
                        settings.default_exclude_words if settings 
                        else config.DEFAULT_EXCLUDE_WORDS
                    )
                
                    chat = Chat(
                        id=chat_id, 
                        title=chat_title or f"Чат {chat_id}",
                        message_limit=config.DEFAULT_MESSAGE_LIMIT,
                        exclude_words=default_exceptions,
                        exclude_use_regex=config.DEFAULT_EXCLUDE_USE_REGEX,
                        notification_texts=config.DEFAULT_NOTIFICATIONS
                    )
                    session.add(chat)
                    await session.commit()
                    await session.refresh(chat)
                else:
                    # ВСЕГДА обновляем название чата, если оно передано
                    if chat_title and chat.title != chat_title:
                        chat.title = chat_title
                        await session.commit()
            
            return chat
        except Exception as e:
            print(f"⚠️ Ошибка при работе с чатом {chat_id}: {e}")
            return None
    
    async def get_or_create_user(self, user_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None) -> User:
        """Получить или создать пользователя в БД"""
        if not self.async_session:
            return User(id=user_id, username=username, first_name=first_name or "")
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    user = User(
                        id=user_id,
                        username=username,
                        first_name=first_name or "",
                        last_name=last_name
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                
                return user
        except Exception as e:
            print(f"⚠️ Ошибка при работе с пользователем: {e}")
            return User(id=user_id, username=username, first_name=first_name or "")
    
    async def get_or_create_user_chat_data(self, user_id: int, chat_id: int) -> UserChatData:
        """Получить или создать данные пользователя в чате (всегда создает запись)"""
        if not self.is_valid_chat_id(chat_id):
            # Создаем временный объект
            return UserChatData(user_id=user_id, chat_id=chat_id, message_count=0)
        
        if not self.async_session:
            return UserChatData(user_id=user_id, chat_id=chat_id, message_count=0)
        
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
            
                if not user_chat_data:
                    # ВСЕГДА создаем запись, даже если пользователь только что присоединился
                    user_chat_data = UserChatData(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_count=0,
                        last_reset_date=datetime.utcnow()
                    )
                    session.add(user_chat_data)
                    await session.commit()
                    await session.refresh(user_chat_data)
            
                return user_chat_data
        except Exception as e:
            print(f"⚠️ Ошибка при работе с user_chat_data: {e}")
            # Возвращаем временный объект в случае ошибки
            return UserChatData(user_id=user_id, chat_id=chat_id, message_count=0)
    
    async def update_message_count(self, user_id: int, chat_id: int) -> int:
        """Увеличивает счетчик сообщений и возвращает новое значение"""
        if not self.is_valid_chat_id(chat_id):
            return 0
            
        if not self.async_session:
            return 1
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
                
                if not user_chat_data:
                    user_chat_data = UserChatData(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_count=1,
                        last_reset_date=datetime.utcnow()
                    )
                    session.add(user_chat_data)
                else:
                    user_chat_data.message_count += 1
                    user_chat_data.updated_at = datetime.utcnow()
                
                await session.commit()
                await session.refresh(user_chat_data)
                
                return user_chat_data.message_count
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении счетчика: {e}")
            return 1
    
    async def get_all_chats(self) -> list:
        """Получить все чаты из БД"""
        if not self.async_session:
            return []
            
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Chat).where(Chat.id < -99)
                )
                chats = result.scalars().all()
                
                valid_chats = []
                for chat in chats:
                    if self.is_valid_chat_id(chat.id):
                        valid_chats.append(chat)
                
                return valid_chats
        except Exception as e:
            print(f"⚠️ Ошибка при получении чатов: {e}")
            return []
    
    async def get_chat_by_id(self, chat_id: int) -> Chat:
        """Получить чат по ID"""
        if not self.is_valid_chat_id(chat_id):
            return None
            
        if not self.async_session:
            return None
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            print(f"⚠️ Ошибка при получении чата {chat_id}: {e}")
            return None
    
    async def update_chat_limit(self, chat_id: int, new_limit: int) -> bool:
        """Обновить лимит сообщений для чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if chat:
                    chat.message_limit = new_limit
                    await session.commit()
                    return True
                return False
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении лимита чата: {e}")
            return False
    
    async def update_user_limit(self, user_id: int, chat_id: int, new_limit: int = None) -> bool:
        """Обновить индивидуальный лимит для пользователя в чате"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
                
                if not user_chat_data:
                    return False
                
                user_chat_data.custom_limit = new_limit
                user_chat_data.is_custom_limit_active = new_limit is not None
                if new_limit is not None:
                    user_chat_data.last_custom_reset_date = datetime.utcnow()
                else:
                    user_chat_data.last_custom_reset_date = None
                
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении лимита пользователя: {e}")
            return False
    
    async def get_user_limit(self, user_id: int, chat_id: int) -> int:
        """Получает лимит для пользователя с учетом временных лимитов"""
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                from .models.schemas import UserChatData, Chat

                # Получаем данные пользователя
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()

                # Получаем настройки чата
                result = await session.execute(
                    select(Chat)
                    .where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
                chat_limit = chat.message_limit if chat else 5

                # НОВАЯ ЛОГИКА: Проверяем временный лимит
                if user_chat_data and user_chat_data.custom_limit:
                    # Если есть дата истечения
                    if user_chat_data.custom_limit_expires_at:
                        if datetime.utcnow() < user_chat_data.custom_limit_expires_at:
                            # Временный лимит активен
                            print(f"   ✅ Временный лимит активен: {user_chat_data.custom_limit} до {user_chat_data.custom_limit_expires_at}")
                            return user_chat_data.custom_limit
                        else:
                            # Временный лимит истек
                            print(f"   ⏰ Временный лимит истек")
                            user_chat_data.custom_limit = None
                            user_chat_data.custom_limit_expires_at = None
                            user_chat_data.is_custom_limit_active = False
                            # СБРАСЫВАЕМ счетчик сообщений при истечении временного лимита
                            user_chat_data.message_count = 0
                            user_chat_data.last_reset_date = datetime.utcnow()
                        
                            await session.commit()
                            print(f"   🔄 Счетчик сброшен после истечения временного лимита")
                            return chat_limit
                    else:
                        # Постоянный индивидуальный лимит (старая логика)
                        print(f"   ⭐ Постоянный лимит: {user_chat_data.custom_limit}")
                        return user_chat_data.custom_limit

                # Возвращаем лимит чата или дефолтный
                print(f"   📊 Лимит чата: {chat_limit}")
                return chat_limit

        except Exception as e:
            print(f"❌ Ошибка получения лимита пользователя: {e}")
            return 5
    
    async def get_user_data_with_days(self, user_id: int, chat_id: int) -> dict:
        """Получает данные пользователя с расчетом дней до сброса"""
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                from .models.schemas import UserChatData, Chat
    
                result = await session.execute(
                    select(UserChatData, Chat)
                    .join(Chat, UserChatData.chat_id == Chat.id)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                row = result.first()
    
                if not row:
                    return None
    
                user_chat_data, chat = row
    
                # Получаем текущий лимит - определяем логику прямо здесь
                user_limit = await self._get_user_limit_internal(session, user_id, chat_id, user_chat_data, chat)
    
                # Проверяем, не истек ли временный лимит
                if user_chat_data.custom_limit_expires_at:
                    if datetime.utcnow() > user_chat_data.custom_limit_expires_at:
                        # Временный лимит истек
                        user_chat_data.custom_limit = None
                        user_chat_data.custom_limit_expires_at = None
                        await session.commit()
                        # Обновляем лимит
                        user_limit = await self._get_user_limit_internal(session, user_id, chat_id, user_chat_data, chat)
    
                is_custom = user_chat_data.custom_limit is not None
    
                # Расчет дней
                if user_chat_data.custom_limit_expires_at:
                    # Для временных лимитов
                    days_left = (user_chat_data.custom_limit_expires_at - datetime.utcnow()).days
                    days_left = max(0, days_left)
                else:
                    # Для обычных лимитов
                    now = datetime.utcnow()
                    if now.day == 1:
                        next_reset = now.replace(day=1) + timedelta(days=32)
                        next_reset = next_reset.replace(day=1)
                    else:
                        next_reset = now.replace(day=1) + timedelta(days=32)
                        next_reset = next_reset.replace(day=1)
        
                    days_left = (next_reset - now).days
    
                return {
                    'user_chat_data': user_chat_data,
                    'user_limit': user_limit,
                    'days_left': days_left,
                    'is_custom': is_custom
                }
    
        except Exception as e:
            print(f"❌ Ошибка получения данных пользователя: {e}")
            return None

    async def _get_user_limit_internal(self, session, user_id, chat_id, user_chat_data, chat):
        """Вспомогательная функция для получения лимита"""
        # Проверяем временный лимит
        if user_chat_data.custom_limit:
            if user_chat_data.custom_limit_expires_at:
                if datetime.utcnow() < user_chat_data.custom_limit_expires_at:
                    # Активный временный лимит
                    return user_chat_data.custom_limit
                else:
                 # Истекший временный лимит
                    return chat.message_limit if chat else 5
        else:
                # Постоянный индивидуальный лимит
                return user_chat_data.custom_limit

    # Лимит чата или дефолтный
        return chat.message_limit if chat else 5

    async def get_user_limit(self, user_id: int, chat_id: int) -> int:
        """Получает лимит для пользователя с учетом временных лимитов"""
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                from .models.schemas import UserChatData, Chat
        
                # Получаем данные пользователя
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
        
                # Получаем настройки чата
                result = await session.execute(
                    select(Chat)
                    .where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
        
                # Проверяем временный лимит
                if user_chat_data and user_chat_data.custom_limit:
                    # Если есть дата истечения и она еще не наступила
                    if user_chat_data.custom_limit_expires_at:
                        if datetime.utcnow() < user_chat_data.custom_limit_expires_at:
                            # Временный лимит активен
                            return user_chat_data.custom_limit
                        else:
                            # Временный лимит истек, сбрасываем
                            user_chat_data.custom_limit = None
                            user_chat_data.custom_limit_expires_at = None
                            await session.commit()
                            # Возвращаем лимит чата
                            return chat.message_limit if chat else 5
                    else:
                        # Постоянный индивидуальный лимит (старая логика)
                        return user_chat_data.custom_limit
        
                # Возвращаем лимит чата или дефолтный
                return chat.message_limit if chat else 5
        
        except Exception as e:
            print(f"❌ Ошибка получения лимита пользователя: {e}")
            return 5
    async def get_global_settings(self):
        """Получить глобальные настройки"""
        print(f"🔧 DEBUG get_global_settings: Запрос настроек")
    
        if not self.async_session:
            print("   ⚠️ Нет сессии, возвращаю None")
            return None
        
        try:
            async with self.async_session() as session:
                # Используем session.get для получения объекта
                settings = await session.get(GlobalSettings, 1)
            
                print(f"   🔧 Настройки найдены: {settings is not None}")
            
                if not settings:
                    print("ℹ️ Настроек нет, создаю")
                    settings = GlobalSettings(
                        default_message_limit=config.DEFAULT_MESSAGE_LIMIT,
                        default_exclude_words=config.DEFAULT_EXCLUDE_WORDS,
                        default_exclude_use_regex=config.DEFAULT_EXCLUDE_USE_REGEX,
                        default_notifications=config.DEFAULT_NOTIFICATIONS,
                        default_banned_words=["хуй", "пизда", "еблан", "мудак", "сука", "блять"],
                        default_min_message_length=20,
                        contact_link="",
                        auto_unblock_days=30,
                        security_log_enabled=True
                    )
                    session.add(settings)
                    await session.commit()
                    await session.refresh(settings)
                    print(f"✅ Созданы настройки: empty_message = {settings.default_notifications.get('empty_message', 'НЕТ')[0:30]}...")
            
                print(f"   📊 Возвращаю настройки: empty_message = {settings.default_notifications.get('empty_message', 'НЕТ')[0:30]}...")
                return settings
        except Exception as e:
            print(f"⚠️ Ошибка получения глобальных настроек: {e}")
            return None
    
    async def update_global_settings(self, contact_link: str = None, default_limit: int = None, 
                                   auto_unblock_days: int = None, security_log_enabled: bool = None) -> bool:
        """Обновить глобальные настройки"""
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
                
                if not settings:
                    settings = GlobalSettings()
                    session.add(settings)
                
                if contact_link is not None:
                    settings.contact_link = contact_link
                
                if default_limit is not None:
                    settings.default_message_limit = default_limit
                
                if auto_unblock_days is not None:
                    settings.auto_unblock_days = auto_unblock_days
                
                if security_log_enabled is not None:
                    settings.security_log_enabled = security_log_enabled
                
                settings.updated_at = datetime.utcnow()
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка обновления глобальных настроек: {e}")
            return False
    
    async def update_global_exceptions(self, exceptions: list, use_regex: bool = None) -> bool:
        """Обновить глобальные исключения"""
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
                
                if not settings:
                    settings = GlobalSettings()
                    session.add(settings)
                
                settings.default_exclude_words = exceptions
                
                if use_regex is not None:
                    settings.default_exclude_use_regex = use_regex
                
                settings.updated_at = datetime.utcnow()
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка обновления глобальных исключений: {e}")
            return False
    
    async def update_global_notifications(self, notifications: dict) -> bool:
        """Обновить глобальные уведомления"""
        print(f"🔄 DEBUG [update_global_notifications]: Начало, сессия: {self.async_session is not None}")
    
        if not self.async_session:
            print("❌ DEBUG: Нет сессии")
            return False
        
        try:
            async with self.async_session() as session:
                print("🔧 DEBUG: Сессия создана")
            
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
            
                print(f"🔧 DEBUG: Настройки найдены: {settings is not None}")
            
                if not settings:
                    print("ℹ️ DEBUG: Создаем новые настройки")
                    settings = GlobalSettings()
                    session.add(settings)
            
                print(f"🔧 DEBUG: Старые уведомления: {settings.default_notifications}")
                print(f"🔧 DEBUG: Новые уведомления: {notifications}")
            
                settings.default_notifications = notifications
                settings.updated_at = datetime.utcnow()
            
                await session.commit()
                print("✅ DEBUG: Коммит успешен")
            
                # Обновляем объект после коммита
                await session.refresh(settings)
                print(f"✅ DEBUG: Проверка после коммита: {settings.default_notifications}")
            
                return True
            
        except Exception as e:
            print(f"❌ DEBUG: Ошибка обновления глобальных уведомлений: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    
    async def init_global_settings(self):
        """Инициализация глобальных настроек"""
        if not self.async_session:
            return
    
        try:
            async with self.async_session() as session:
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
        
                if not settings:
                    # Создаем с ПОЛНЫМ набором уведомлений
                    settings = GlobalSettings(
                        default_message_limit=config.DEFAULT_MESSAGE_LIMIT,
                        default_exclude_words=config.DEFAULT_EXCLUDE_WORDS,
                        default_exclude_use_regex=config.DEFAULT_EXCLUDE_USE_REGEX,
                        default_notifications=config.DEFAULT_NOTIFICATIONS,  # Теперь с новыми ключами
                        default_banned_words=["хуй", "пизда", "еблан", "мудак", "сука", "блять"],
                        default_min_message_length=20,
                        contact_link="",
                        auto_unblock_days=30,
                        security_log_enabled=True
                    )
                    session.add(settings)
                    await session.commit()
                    print("✅ Глобальные настройки созданы с полным набором уведомлений")
                else:
                    # Проверяем и добавляем НОВЫЕ уведомления если их нет
                    if settings.default_notifications:
                        current_notifications = settings.default_notifications

                        # Добавляем новые ключи если их нет
                        if 'empty_message_blocked' not in current_notifications:
                            current_notifications['empty_message_blocked'] = config.DEFAULT_NOTIFICATIONS['empty_message_blocked']

                        if 'swear_word_blocked' not in current_notifications:
                            current_notifications['swear_word_blocked'] = config.DEFAULT_NOTIFICATIONS['swear_word_blocked']

                        settings.default_notifications = current_notifications
                        await session.commit()
                        print("✅ Добавлены новые уведомления в существующие настройки")
                
                    # Проверяем default_banned_words (старое)
                    if not hasattr(settings, 'default_banned_words'):
                        settings.default_banned_words = ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
                        await session.commit()
                        print("✅ Добавлено поле default_banned_words")
        except Exception as e:
            print(f"⚠️ Ошибка инициализации настроек: {e}")

    async def get_chat_exceptions(self, chat_id: int) -> list:
        """Получить список исключений для чата"""
        if not self.is_valid_chat_id(chat_id):
            return []
            
        if not self.async_session:
            return config.DEFAULT_EXCLUDE_WORDS
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if chat and chat.exclude_words:
                    return chat.exclude_words
                
                # Если в чате нет исключений, возвращаем глобальные
                settings = await self.get_global_settings()
                if settings and settings.default_exclude_words:
                    return settings.default_exclude_words
                    
                return config.DEFAULT_EXCLUDE_WORDS
        except Exception as e:
            print(f"⚠️ Ошибка получения исключений: {e}")
            return config.DEFAULT_EXCLUDE_WORDS
    
    async def get_chat_exclude_regex(self, chat_id: int) -> bool:
        """Получить настройку использования regex для исключений чата"""
        if not self.is_valid_chat_id(chat_id):
            return config.DEFAULT_EXCLUDE_USE_REGEX
            
        if not self.async_session:
            return config.DEFAULT_EXCLUDE_USE_REGEX
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if chat and chat.exclude_use_regex is not None:
                    return chat.exclude_use_regex
                    
                # Если в чате нет настройки, возвращаем глобальную
                settings = await self.get_global_settings()
                if settings and settings.default_exclude_use_regex is not None:
                    return settings.default_exclude_use_regex
                    
                return config.DEFAULT_EXCLUDE_USE_REGEX
        except Exception as e:
            print(f"⚠️ Ошибка получения настроек regex: {e}")
            return config.DEFAULT_EXCLUDE_USE_REGEX
    
    async def update_chat_exceptions(self, chat_id: int, exceptions: list, use_regex: bool = None) -> bool:
        """Обновить исключения для чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if not chat:
                    return False
                
                chat.exclude_words = exceptions
                
                if use_regex is not None:
                    chat.exclude_use_regex = use_regex
                
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка обновления исключений чата: {e}")
            return False
    
    async def add_exception_word(self, chat_id: int, word: str) -> bool:
        """Добавить слово в исключения для чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if not chat:
                    return False
                
                # Инициализируем список исключений если его нет
                if chat.exclude_words is None:
                    chat.exclude_words = []
                
                # Добавляем слово если его еще нет
                word_lower = word.lower().strip()
                if word_lower not in [w.lower() for w in chat.exclude_words]:
                    chat.exclude_words.append(word)
                    await session.commit()
                    return True
                
                return False
        except Exception as e:
            print(f"⚠️ Ошибка добавления исключения: {e}")
            return False
    
    async def remove_exception_word(self, chat_id: int, word: str) -> bool:
        """Удалить слово из исключений чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if not chat or not chat.exclude_words:
                    return False
                
                # Удаляем слово
                word_lower = word.lower().strip()
                new_exclude_words = [w for w in chat.exclude_words if w.lower() != word_lower]
                
                if len(new_exclude_words) != len(chat.exclude_words):
                    chat.exclude_words = new_exclude_words
                    await session.commit()
                    return True
                
                return False
        except Exception as e:
            print(f"⚠️ Ошибка удаления исключения: {e}")
            return False
    
    async def reset_chat_exceptions(self, chat_id: int) -> bool:
        """Сбросить исключения чата к глобальным настройкам"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if not chat:
                    return False
                
                # Получаем глобальные настройки
                settings = await self.get_global_settings()
                if settings:
                    chat.exclude_words = settings.default_exclude_words
                    chat.exclude_use_regex = settings.default_exclude_use_regex
                else:
                    chat.exclude_words = config.DEFAULT_EXCLUDE_WORDS
                    chat.exclude_use_regex = config.DEFAULT_EXCLUDE_USE_REGEX
                
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка сброса исключений: {e}")
            return False
    
    async def get_chat_notifications(self, chat_id: int) -> dict:
        """Получить настройки уведомлений для чата"""
        print(f"🔧 DEBUG get_chat_notifications: Запрос для чата {chat_id}")
    
        if not self.is_valid_chat_id(chat_id):
            print("   ⚠️ Невалидный ID чата, возвращаю глобальные")
            settings = await self.get_global_settings()
            result = settings.default_notifications if settings else config.DEFAULT_NOTIFICATIONS
            print(f"   📊 Результат: {list(result.keys())}")
            return result
        
        if not self.async_session:
            print("   ⚠️ Нет сессии, возвращаю глобальные")
            settings = await self.get_global_settings()
            result = settings.default_notifications if settings else config.DEFAULT_NOTIFICATIONS
            print(f"   📊 Результат: {list(result.keys())}")
            return result
        
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
                # Получаем глобальные настройки
                global_settings = await self.get_global_settings()
                print(f"   🔧 Глобальные настройки найдены: {global_settings is not None}")
            
                if global_settings:
                    print(f"   📝 Глобальные уведомления: {global_settings.default_notifications.get('empty_message', 'НЕТ')[0:30]}...")
            
                base_notifications = global_settings.default_notifications if global_settings else config.DEFAULT_NOTIFICATIONS
            
                if chat and chat.custom_notifications:
                    print(f"   🔧 У чата есть custom_notifications: {chat.custom_notifications}")
                    # Объединяем с глобальными настройками
                    notifications = base_notifications.copy()
                    notifications.update(chat.custom_notifications)
                    print(f"   📊 Объединенный результат: {notifications.get('empty_message', 'НЕТ')[0:30]}...")
                    return notifications
                elif chat and chat.notification_texts:
                    print(f"   🔧 У чата есть notification_texts: {chat.notification_texts}")
                    return chat.notification_texts
                else:
                    print(f"   🔧 У чата нет кастомных уведомлений, возвращаю глобальные")
                    print(f"   📊 Глобальные уведомления: {base_notifications.get('empty_message', 'НЕТ')[0:30]}...")
                    return base_notifications
        except Exception as e:
            print(f"⚠️ Ошибка получения уведомлений чата: {e}")
            settings = await self.get_global_settings()
            result = settings.default_notifications if settings else config.DEFAULT_NOTIFICATIONS
            return result
    
    async def update_chat_notifications(self, chat_id: int, notifications: dict) -> bool:
        """Обновить настройки уведомлений для чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if chat:
                    chat.custom_notifications = notifications
                    await session.commit()
                    return True
                return False
        except Exception as e:
            print(f"⚠️ Ошибка обновления уведомлений чата: {e}")
            return False
    
    async def update_chat_banned_words(self, chat_id: int, words: list) -> bool:
        """Обновить запрещенные слова для чата"""
        if not self.is_valid_chat_id(chat_id):
            return False
        
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                from .models.schemas import Chat
            
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
                if not chat:
                    return False
            
                chat.banned_words = words
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка обновления запрещенных слов чата: {e}")
            return False
    async def get_chat_banned_words(self, chat_id: int) -> list:
        """Получить запрещенные слова для чата"""
        if not self.is_valid_chat_id(chat_id):
            return []
        
        try:
            async with self.async_session() as session:
                from sqlalchemy import select
                from .models.schemas import Chat
            
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
            
            if chat and hasattr(chat, 'banned_words') and chat.banned_words:
                    return chat.banned_words
            
                # Если нет в чате, возвращаем глобальные
            return await self.get_global_banned_words()
        except Exception as e:
            print(f"⚠️ Ошибка получения запрещенных слов чата: {e}")
            return await self.get_global_banned_words()
    

    async def reset_chat_notifications(self, chat_id: int) -> bool:
        """Сбросить уведомления чата к стандартным"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id)
                )
                chat = result.scalar_one_or_none()
                
                if chat:
                    chat.custom_notifications = {}
                    await session.commit()
                    return True
                return False
        except Exception as e:
            print(f"⚠️ Ошибка сброса уведомлений: {e}")
            return False
    
    async def check_exception_match(self, text: str, chat_id: int) -> bool:
        """Проверить, попадает ли текст под исключения"""
        if not text:
            return False
        
        exceptions = await self.get_chat_exceptions(chat_id)
        if not exceptions:
            return False
        
        use_regex = await self.get_chat_exclude_regex(chat_id)
        text_lower = text.lower()
        
        for pattern in exceptions:
            pattern = pattern.strip()
            if not pattern:
                continue
                
            if use_regex:
                try:
                    # Попробуем скомпилировать как regex
                    if re.search(pattern, text, re.IGNORECASE):
                        return True
                except re.error:
                    # Если не валидный regex, ищем как обычную строку
                    if pattern.lower() in text_lower:
                        return True
            else:
                if pattern.lower() in text_lower:
                    return True
        
        return False
    
    async def log_action(self, action_type: str, user_id: int = None, 
                        chat_id: int = None, details: str = None) -> bool:
        """Логирование действий"""
        if not self.async_session:
            return False
            
        try:
            # Проверяем, включено ли логирование
            settings = await self.get_global_settings()
            if settings and not settings.security_log_enabled:
                return True
            
            async with self.async_session() as session:
                from sqlalchemy import insert
                
                log_entry = {
                    "action_type": action_type,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "details": details,
                    "created_at": datetime.utcnow()
                }
                
                await session.execute(
                    insert(ActionLog).values(**log_entry)
                )
                await session.commit()
                
                # Также пишем в консоль с цветами
                colors = {
                    "message_received": "📨",
                    "user_blocked": "🔒",
                    "warning_sent": "⚠️",
                    "empty_message_deleted": "🗑️",
                    "message_excepted": "📝",
                    "bot_added_to_chat": "🤖",
                    "bot_removed_from_chat": "❌"
                }
                
                icon = colors.get(action_type, "📋")
                print(f"{icon} [LOG] {action_type}: user={user_id}, chat={chat_id}, details={details}")
                return True
        except Exception as e:
            print(f"⚠️ Ошибка логирования: {e}")
            return False
    
    async def get_general_statistics(self) -> dict:
        """Получить общую статистику"""
        if not self.async_session:
            return {}
            
        try:
            async with self.async_session() as session:
                # Общее количество сообщений
                result = await session.execute(
                    select(func.sum(UserChatData.message_count))
                )
                total_messages = result.scalar() or 0
                
                # Количество пользователей
                result = await session.execute(
                    select(func.count(UserChatData.user_id.distinct()))
                )
                total_users = result.scalar() or 0
                
                # Количество чатов
                result = await session.execute(
                    select(func.count(Chat.id))
                )
                total_chats = result.scalar() or 0
                
                # Заблокированные пользователи
                result = await session.execute(
                    select(func.count(UserChatData.id))
                    .where(UserChatData.is_muted == True)
                )
                blocked_users = result.scalar() or 0
                
                return {
                    "total_messages": total_messages,
                    "total_users": total_users,
                    "total_chats": total_chats,
                    "blocked_users": blocked_users,
                    "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
                }
        except Exception as e:
            print(f"⚠️ Ошибка получения статистики: {e}")
            return {}
    
    async def auto_unblock_users(self) -> int:
        """Автоматическая разблокировка пользователей"""
        if not self.async_session:
            return 0
            
        try:
            async with self.async_session() as session:
                settings = await self.get_global_settings()
                auto_unblock_days = settings.auto_unblock_days if settings else 30
                
                # Находим пользователей, заблокированных более N дней
                cutoff_date = datetime.utcnow() - timedelta(days=auto_unblock_days)
                
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.is_muted == True)
                    .where(UserChatData.mute_until <= cutoff_date)
                )
                users_to_unblock = result.scalars().all()
                
                unblocked_count = 0
                for user_data in users_to_unblock:
                    user_data.is_muted = False
                    user_data.mute_until = None
                    user_data.message_count = 0
                    unblocked_count += 1
                    
                    # Логируем авторазблокировку
                    await self.log_action("auto_unblock", user_id=user_data.user_id, 
                                        chat_id=user_data.chat_id, 
                                        details=f"Авторазблокировка через {auto_unblock_days} дней")
                
                if unblocked_count > 0:
                    await session.commit()
                    print(f"✅ Автоматически разблокировано {unblocked_count} пользователей")
                
                return unblocked_count
        except Exception as e:
            print(f"⚠️ Ошибка авторазблокировки: {e}")
            return 0
    
    async def monthly_reset_counts(self) -> int:
        """Ежемесячный сброс счетчиков (только стандартных лимитов)"""
        if not self.async_session:
            return 0
            
        try:
            async with self.async_session() as session:
                # Сбрасываем только пользователей со стандартными лимитами
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.custom_limit == None)
                    .where(UserChatData.is_muted == True)
                )
                users_to_reset = result.scalars().all()
                
                reset_count = 0
                for user_data in users_to_reset:
                    user_data.message_count = 0
                    user_data.last_reset_date = datetime.utcnow()
                    user_data.is_muted = False
                    user_data.mute_until = None
                    reset_count += 1
                
                # Также сбрасываем счетчики у активных пользователей со стандартными лимитами
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.custom_limit == None)
                    .where(UserChatData.is_muted == False)
                )
                active_users = result.scalars().all()
                
                for user_data in active_users:
                    user_data.message_count = 0
                    user_data.last_reset_date = datetime.utcnow()
                    reset_count += 1
                
                if reset_count > 0:
                    await session.commit()
                    print(f"✅ Ежемесячный сброс: обновлено {reset_count} пользователей")
                
                # Логируем сброс
                await self.log_action("monthly_reset", details=f"Сброшено {reset_count} пользователей")
                
                return reset_count
        except Exception as e:
            print(f"⚠️ Ошибка ежемесячного сброса: {e}")
            await self.log_action("monthly_reset_error", details=f"Ошибка: {str(e)}")
            return 0
    
    async def check_and_reset_expired_custom_limits(self) -> int:
        """Проверяет и сбрасывает истекшие ручные лимиты"""
        if not self.async_session:
            return 0
            
        try:
            async with self.async_session() as session:
                reset_count = 0
                
                # Находим пользователей с ручными лимитами
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.custom_limit != None)
                )
                users_with_custom = result.scalars().all()
                
                for user_data in users_with_custom:
                    if not user_data.last_custom_reset_date:
                        continue
                    
                    # Рассчитываем следующую дату сброса для ручного лимита
                    next_reset = user_data.last_custom_reset_date.replace(day=28) + timedelta(days=4)
                    next_reset = next_reset.replace(day=1)
                    
                    # Если дата сброса наступила
                    if datetime.utcnow() >= next_reset:
                        # Проверяем, не превышен ли лимит
                        if user_data.custom_limit is not None and user_data.message_count >= user_data.custom_limit:
                            # Сбрасываем ручной лимит
                            user_data.custom_limit = None
                            user_data.is_custom_limit_active = False
                            user_data.last_custom_reset_date = None
                            user_data.message_count = 0
                            user_data.last_reset_date = datetime.utcnow()
                            reset_count += 1
                            
                            await self.log_action(
                                "custom_limit_expired", 
                                user_id=user_data.user_id, 
                                chat_id=user_data.chat_id,
                                details="Ручной лимит истек и сброшен"
                            )
                
                if reset_count > 0:
                    await session.commit()
                    print(f"✅ Сброшено истекших ручных лимитов: {reset_count}")
                
                return reset_count
        except Exception as e:
            print(f"⚠️ Ошибка проверки ручных лимитов: {e}")
            return 0
    
    async def reset_user_custom_limit(self, user_id: int, chat_id: int) -> bool:
        """Сбросить ручной лимит пользователя"""
        if not self.is_valid_chat_id(chat_id):
            return False
            
        if not self.async_session:
            return False
            
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
                
                if not user_chat_data:
                    return False
                
                user_chat_data.custom_limit = None
                user_chat_data.is_custom_limit_active = False
                user_chat_data.last_custom_reset_date = None
                user_chat_data.message_count = 0
                user_chat_data.last_reset_date = datetime.utcnow()
                
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка сброса ручного лимита: {e}")
            return False
        
    async def update_global_banned_words(self, words: list) -> bool:
        """Обновить глобальные запрещенные слова"""
        if not self.async_session:
            return False
        
        try:
            async with self.async_session() as session:
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
            
                if not settings:
                    settings = GlobalSettings()
                    session.add(settings)
            
                settings.default_banned_words = words
                settings.updated_at = datetime.utcnow()
                await session.commit()
                return True
        except Exception as e:
            print(f"⚠️ Ошибка обновления запрещенных слов: {e}")
        return False

    async def get_global_banned_words(self) -> list:
        """Получить глобальные запрещенные слова"""
        if not self.async_session:
            # Возвращаем базовый список
            return ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
        
        try:
            async with self.async_session() as session:
                result = await session.execute(select(GlobalSettings))
                settings = result.scalar_one_or_none()
            
                if settings and hasattr(settings, 'default_banned_words'):
                    return settings.default_banned_words or []
            
                # Если нет в БД, возвращаем базовый
                return ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
        except Exception as e:
            print(f"⚠️ Ошибка получения запрещенных слов: {e}")
            return ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
    async def safe_get_chat_exceptions(self, chat_id: int) -> list:
        """Безопасное получение исключений для чата"""
        try:
            result = await self.get_chat_exceptions(chat_id)
            if result is None:
                return []
            elif isinstance(result, list):
                return result
            else:
                print(f"⚠️ Исключения не список: {type(result)}")
                return list(result)
        except Exception as e:
            print(f"⚠️ Ошибка safe_get_chat_exceptions: {e}")
            return []

    async def safe_get_global_banned_words(self) -> list:
        """Безопасное получение глобальных запрещенных слов"""
        try:
            result = await self.get_global_banned_words()
            if result is None:
                return []
            elif isinstance(result, list):
                return result
            else:
                print(f"⚠️ Запрещенные слова не список: {type(result)}")
                return list(result)
        except Exception as e:
            print(f"⚠️ Ошибка safe_get_global_banned_words: {e}")
            return ["хуй", "пизда", "еблан", "мудак", "сука", "блять"]
    async def set_temporary_user_limit(self, user_id: int, chat_id: int, limit: int, days: int) -> bool:
        """Установка временного лимита для пользователя на N дней"""
        try:
            async with self.async_session() as session:
                from .models.schemas import UserChatData
        
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
        
                if not user_chat_data:
                    # Создаем новую запись
                    user_chat_data = UserChatData(
                        user_id=user_id,
                        chat_id=chat_id,
                        custom_limit=limit,
                        custom_limit_expires_at=datetime.utcnow() + timedelta(days=days),
                        message_count=0
                    )
                    session.add(user_chat_data)
                else:
                    # Обновляем существующую запись
                    user_chat_data.custom_limit = limit
                    user_chat_data.custom_limit_expires_at = datetime.utcnow() + timedelta(days=days)
        
                await session.commit()
                return True
        # Очищаем кэш, чтобы изменения сразу вступили в силу
            from .handlers.group import user_empty_message_counters
            key = (user_id, chat_id)
            if key in user_empty_message_counters:
                del user_empty_message_counters[key]
        except Exception as e:
            print(f"❌ Ошибка установки временного лимита: {e}")
            return False

    def check_banned_words(text: str, banned_words: list) -> bool:
        """Проверяет наличие запрещенных слов в тексте"""
        if not text or not banned_words:
            return False
    
        text_lower = text.lower()
        print(f"🔍 Проверка запрещенных слов: текст='{text_lower[:50]}...', запрещенные слова={banned_words}")
    
        for word in banned_words:
            word_lower = word.lower().strip()
            if word_lower and word_lower in text_lower:
                print(f"   🚫 Найдено запрещенное слово: '{word_lower}'")
                return True
    
        print(f"   ✅ Запрещенных слов не найдено")
        return False
    

    async def set_temporary_user_limit(self, user_id: int, chat_id: int, limit: int, days: int) -> bool:
        """Установка временного лимита для пользователя на N дней"""
        try:
            async with self.async_session() as session:
                from .models.schemas import UserChatData

                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()

                if not user_chat_data:
                    # Создаем новую запись
                    user_chat_data = UserChatData(
                        user_id=user_id,
                        chat_id=chat_id,
                        custom_limit=limit,
                        custom_limit_expires_at=datetime.utcnow() + timedelta(days=days),
                        is_custom_limit_active=True,
                        message_count=0,  # СБРАСЫВАЕМ счетчик при установке нового лимита
                        last_reset_date=datetime.utcnow()
                    )
                    session.add(user_chat_data)
                else:
                    # Обновляем существующую запись
                    user_chat_data.custom_limit = limit
                    user_chat_data.custom_limit_expires_at = datetime.utcnow() + timedelta(days=days)
                    user_chat_data.is_custom_limit_active = True
                    # СБРАСЫВАЕМ счетчик при изменении лимита
                    user_chat_data.message_count = 0
                    user_chat_data.last_reset_date = datetime.utcnow()

                await session.commit()
                print(f"✅ Установлен временный лимит {limit} на {days} дней для user={user_id}, chat={chat_id}")
                return True

        except Exception as e:
            print(f"❌ Ошибка установки временного лимита: {e}")
            return False
        
    async def reset_message_count_for_user(user_id: int, chat_id: int) -> None:
        """Сбрасывает счетчик сообщений для пользователя в чате"""
        try:
            async with AsyncSession() as session:
                from .models.schemas import UserChatData
            
                # Получаем или создаем запись
                result = await session.execute(
                    select(UserChatData)
                    .where(UserChatData.user_id == user_id)
                    .where(UserChatData.chat_id == chat_id)
                )
                user_chat_data = result.scalar_one_or_none()
            
                if user_chat_data:
                    user_chat_data.message_count = 0
                    await session.commit()
                    print(f"✅ Счетчик сообщений сброшен для пользователя {user_id} в чате {chat_id}")
        except Exception as e:
            print(f"⚠️ Ошибка сброса счетчика сообщений: {e}")
db = Database()