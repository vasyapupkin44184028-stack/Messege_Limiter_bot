import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def migrate():
    """Миграция базы данных для добавления новых полей"""
    from bot.database import db
    from bot.models.schemas import Base
    
    print("🔄 Начинаю миграцию базы данных...")
    
    try:
        # Создаем таблицы с новой структурой
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Таблицы пересозданы с новой структурой")
        
        # Проверяем и добавляем недостающие колонки
        await db.check_and_add_columns()
        
        print("✅ Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(migrate())