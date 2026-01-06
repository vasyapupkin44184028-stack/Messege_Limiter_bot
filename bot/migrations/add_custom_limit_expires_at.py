
import asyncio
from sqlalchemy import text
from ..database import engine

async def add_custom_limit_expires_at():
    async with engine.begin() as conn:
        # Проверяем, существует ли уже колонка
        result = await conn.execute(text("PRAGMA table_info(user_chat_data)"))
        columns = [row[1] for row in result]
        
        if 'custom_limit_expires_at' not in columns:
            # Добавляем новую колонку
            await conn.execute(text("""
                ALTER TABLE user_chat_data 
                ADD COLUMN custom_limit_expires_at DATETIME
            """))
            print("✅ Добавлено поле custom_limit_expires_at")
        else:
            print("✅ Поле custom_limit_expires_at уже существует")

if __name__ == "__main__":
    asyncio.run(add_custom_limit_expires_at())