"""
Инициализация базы данных
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.schema import CreateTable

from .database import db
from .models.schemas import Base, TemporaryLimit, Chat, User, UserChatData, GlobalSettings, ActionLog, Statistics

async def create_tables_if_not_exist():
    """Создает все таблицы, если они не существуют"""
    try:
        print("📊 Инициализация базы данных...")
        
        # Используем стандартный метод создания всех таблиц
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Все таблицы БД созданы/проверены")
        
        # Дополнительная проверка для временных лимитов
        async with db.async_session() as session:
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='temporary_limits'")
            )
            table_exists = result.scalar() is not None
            
            if not table_exists:
                print("📊 Создаю таблицу временных лимитов...")
                await session.execute(CreateTable(TemporaryLimit.__table__))
                await session.commit()
                print("✅ Таблица временных лимитов создана")
            else:
                print("✅ Таблица временных лимитов уже существует")
                
    except Exception as e:
        print(f"⚠️ Ошибка создания таблиц БД: {e}")
        raise

async def init_database():
    """Инициализация всей базы данных"""
    try:
        # Создаем таблицы
        await create_tables_if_not_exist()
        
        # Инициализируем глобальные настройки
        await db.init_global_settings()
        
        print("✅ База данных полностью инициализирована")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False