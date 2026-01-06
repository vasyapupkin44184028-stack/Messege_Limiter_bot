import asyncio
from bot.database import db
from bot.config import config

async def migrate_notifications():
    """Добавляет новые уведомления в существующую БД"""
    print("🔄 Миграция уведомлений...")
    
    settings = await db.get_global_settings()
    if settings:
        current = settings.default_notifications or {}
        
        # Добавляем новые если их нет
        if 'empty_message_blocked' not in current:
            current['empty_message_blocked'] = config.DEFAULT_NOTIFICATIONS['empty_message_blocked']
        
        if 'swear_word_blocked' not in current:
            current['swear_word_blocked'] = config.DEFAULT_NOTIFICATIONS['swear_word_blocked']
        
        settings.default_notifications = current
        async with db.async_session() as session:
            await session.merge(settings)
            await session.commit()
        
        print("✅ Новые уведомления добавлены в БД")
    else:
        print("❌ Настройки не найдены")

if __name__ == "__main__":
    asyncio.run(migrate_notifications())