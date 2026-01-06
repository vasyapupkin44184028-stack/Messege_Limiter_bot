import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from datetime import datetime, timedelta


# Для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# Импорт БД будет внутри функций
db = None

async def cleanup_old_caches():
    """Очистка старых кэшей"""
    print("🧹 Очистка старых кэшей...")
    
    # Здесь можно добавить логику очистки
    # Например, кэши старше 24 часов
    
    print("✅ Очистка кэшей завершена")

async def check_inactive_chats(bot):
    """Проверяет чаты, где бот не является администратором и деактивирует их"""
    try:
        chats = await db.get_all_chats()
        
        for chat in chats:
            if chat.is_active:
                try:
                    # Проверяем права бота в чате
                    bot_member = await bot.get_chat_member(chat.id, bot.id)
                    
                    if bot_member.status in ["kicked", "left"]:
                        # Бота удалили из чата
                        logger.warning(f"   🚫 Бот удален из чата {chat.id}, деактивируем")
                        chat.is_active = False
                        async with db.async_session() as session:
                            await session.merge(chat)
                            await session.commit()
                    
                    elif bot_member.status not in ["administrator", "creator"]:
                        # Бот не админ
                        logger.warning(f"   ⚠️ Бот не админ в чате {chat.id}, деактивируем")
                        chat.is_active = False
                        async with db.async_session() as session:
                            await session.merge(chat)
                            await session.commit()
                            
                except Exception as e:
                    error_msg = str(e).lower()
                    if "kicked" in error_msg or "forbidden" in error_msg:
                        # Бота удалили
                        logger.warning(f"   🚫 Бот удален из чата {chat.id} (ошибка: {e}), деактивируем")
                        chat.is_active = False
                        async with db.async_session() as session:
                            await session.merge(chat)
                            await session.commit()
                    else:
                        # Другая ошибка
                        logger.warning(f"   ⚠️ Не могу проверить права в чате {chat.id}: {e}")
                    
    except Exception as e:
        logger.error(f"⚠️ Ошибка проверки активных чатов: {e}")

async def startup(bot):
    """Действия при запуске бота"""
    global db
    
    print("🤖 Инициализация бота...")
    
    try:
        # Инициализация БД
        from .database import db as database_module
        db = database_module
        
        # Создаем таблицы в БД
        await db.create_tables()
        logger.info("   ✅ Таблицы БД созданы/проверены")
        
        # Инициализируем глобальные настройки
        await db.init_global_settings()
        logger.info("   ✅ Глобальные настройки инициализированы")
        
        # Очищаем старые кэши
        await cleanup_old_caches()
        
        # Проверяем и деактивируем неактивные чаты
        await check_inactive_chats(bot)
        
        # Автоматическая разблокировка пользователей
        unblocked = await db.auto_unblock_users()
        if unblocked > 0:
            print(f"✅ Автоматически разблокировано {unblocked} пользователей")
        
        # Ежемесячный сброс счетчиков (если сегодня 1-е число)
        if datetime.now().day == 1:
            reset_count = await db.monthly_reset_counts()
            if reset_count > 0:
                print(f"✅ Ежемесячный сброс: обновлено {reset_count} пользователей")
        
        # Проверяем истекшие ручные лимиты
        custom_limits_reset = await db.check_and_reset_expired_custom_limits()
        if custom_limits_reset > 0:
            print(f"✅ Сброшено {custom_limits_reset} истекших ручных лимитов")
        
        print("✅ Бот готов к работе!")
        
    except ImportError as e:
        logger.error(f"❌ ОШИБКА импорта модулей: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ ОШИБКА инициализации: {e}")
        raise

async def main():
    """Основная функция запуска бота"""
    logger.info("="*50)
    logger.info("🚀 ЗАПУСК MESSAGE LIMITER BOT")
    logger.info("="*50)
    
    # Импортируем конфиг
    from .config import config
    
    # Проверяем токен
    if not config.BOT_TOKEN or config.BOT_TOKEN == "ВАШ_ТОКЕН_ЗДЕСЬ":
        logger.error("❌ ОШИБКА: Не указан BOT_TOKEN в config.py или .env файле!")
        logger.error("Добавьте токен в .env файл:")
        logger.error("BOT_TOKEN=ваш_токен_здесь")
        return
    
    # Инициализация бота
    logger.info("🤖 Инициализирую бота...")
    try:
        bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        me = await bot.get_me()
        logger.info(f"✅ Бот подключен: @{me.username} (ID: {me.id})")
        logger.info(f"📛 Имя бота: {me.first_name}")
    except Exception as e:
        logger.error(f"❌ ОШИБКА подключения бота: {e}")
        logger.error("Проверьте токен и интернет-соединение")
        return
    
    # Инициализация диспетчера
    logger.info("🔄 Инициализирую диспетчер...")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Проверяем администраторов
    logger.info("👮 Проверяю администраторов...")
    try:
        from .utils.admin_check import get_admin_ids
        admin_ids = get_admin_ids()
        if admin_ids:
            logger.info(f"   ✅ Найдено администраторов: {len(admin_ids)}")
            for admin_id in admin_ids:
                logger.info(f"      • ID: {admin_id}")
        else:
            logger.warning("   ⚠️ Администраторы не найдены в ADMIN_ID.txt")
            logger.warning("   Бот будет доступен только для пользователей из ADMIN_ID.txt")
    except Exception as e:
        logger.warning(f"   ⚠️ Ошибка загрузки администраторов: {e}")
    
    # Регистрируем ВСЕ обработчики в правильном порядке
    logger.info("📝 Регистрирую обработчики...")
    
# Попробуйте так:
    try:
        # Импортируем через модули
        from bot.handlers.commands import router as commands_router
        from bot.handlers.callbacks import router as callbacks_router
        from bot.handlers.group import router as group_router
        from bot.handlers.exceptions import router as exceptions_router
        from bot.handlers.notifications import router as notifications_router
    
        # 1. Сначала команды (они должны обрабатываться первыми, ТОЛЬКО в личных сообщениях)
        dp.include_router(commands_router)
        logger.info("   ✅ Команды для личных сообщений зарегистрированы")
    
        # 2. Затем callback-обработчики (кнопки)
        dp.include_router(callbacks_router)
        dp.include_router(exceptions_router)
        dp.include_router(notifications_router)
        logger.info("   ✅ Callback-обработчики зарегистрированы")
    
        # 3. ПОСЛЕДНИМИ - обработчики групп (важен порядок!)
        dp.include_router(group_router)
        logger.info("   ✅ Групповые обработчики зарегистрированы")
    
    except ImportError as e:
        logger.error(f"❌ ОШИБКА импорта обработчиков: {e}")
        logger.error(f"❌ Импорт завершился с ошибкой: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    except Exception as e:
        logger.error(f"❌ ОШИБКА регистрации обработчиков: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # Запускаем инициализацию при старте
    try:
        await startup(bot)
    except Exception as e:
        logger.error(f"❌ ОШИБКА инициализации при старте: {e}")
        logger.error("Бот может работать некорректно")
    
    # Запуск планировщика задач
    logger.info("⏰ Запускаю планировщик задач...")
    try:
        from .services.scheduler import start_scheduler
        await start_scheduler()
        logger.info("   ✅ Планировщик запущен")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка планировщика: {e}")
        logger.warning("Автоматические задачи не будут выполняться")
    
    # Показываем сводную информацию
    logger.info("="*50)
    logger.info("🎯 БОТ УСПЕШНО ЗАПЕЩЕН!")
    logger.info("="*50)
    logger.info(f"🤖 Бот: @{me.username}")
    logger.info(f"🔗 Ссылка: https://t.me/{me.username}")
    logger.info(f"👮 Администраторов: {len(admin_ids) if 'admin_ids' in locals() else 0}")
    logger.info("="*50)
    logger.info("📱 КОМАНДЫ ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ:")
    logger.info("• /start - Главное меню / Мои лимиты")
    logger.info("• /help - Помощь")
    logger.info("• /id - ID чата")
    logger.info("• /status - Статус бота")
    logger.info("• /test - Проверка работы")
    logger.info("• /debug - Отладочная информация")
    logger.info("="*50)
    logger.info("👮‍♂️ КОМАНДЫ ДЛЯ АДМИНИСТРАТОРОВ:")
    logger.info("• /admin_stats - Статистика бота")
    logger.info("• /admin_list - Список администраторов")
    logger.info("• /export_stats - Экспорт статистики")
    logger.info("="*50)
    logger.info("💬 КОМАНДЫ ДЛЯ ГРУПП:")
    logger.info("• /ботстатус - Статус бота в группе")
    logger.info("• /мойстатус - Ваш статус в группе")
    logger.info("• /статусчата - Статус чата в БД")
    logger.info("• любое сообщение - автоматический учет")
    logger.info("="*50)
    logger.info("⚙️ ФУНКЦИОНАЛЬНОСТЬ:")
    logger.info("✅ Учет сообщений с лимитом")
    logger.info("✅ Удаление 'пустых' сообщений")
    logger.info("✅ Блокировка при превышении лимита")
    logger.info("✅ Автосброс 1-го числа")
    logger.info("✅ Авторазблокировка")
    logger.info("✅ Админ-панель в ЛС")
    logger.info("✅ Разделение прав: пользователи/админы")
    logger.info("✅ Ежемесячная статистика")
    logger.info("✅ Цветовое форматирование (красный/серый)")
    logger.info("✅ Иконки ⭐ для ручных лимитов")
    logger.info("✅ Полное управление исключениями")
    logger.info("✅ Регулярные выражения в исключениях")
    logger.info("✅ Настройка уведомлений")
    logger.info("✅ Раздельные настройки для чатов")
    logger.info("="*50)
    logger.info("🔐 ДОСТУП:")
    logger.info("• Обычные пользователи: видят только свои лимиты")
    logger.info("• Администраторы: полный доступ к управлению")
    logger.info("• Админы указаны в файле ADMIN_ID.txt")
    logger.info("="*50)
    logger.info("⏰ АВТОМАТИЧЕСКИЕ ЗАДАЧИ:")
    logger.info("• Ежемесячный сброс: 1-го числа, 00:01")
    logger.info("• Ежедневная проверка: каждый день, 03:00")
    logger.info("• Резервное копирование: воскресенье, 04:00")
    logger.info("• Проверка ручных лимитов: каждый день, 05:00")
    logger.info("="*50)
    logger.info("📊 НОВЫЕ ВОЗМОЖНОСТИ:")
    logger.info("• Расчет дней до сброса лимитов")
    logger.info("• Логика работы с ручными лимитами")
    logger.info("• Глобальные и чатовые исключения")
    logger.info("• Настройка уведомлений с переменными")
    logger.info("• Сохранение всех настроек в БД")
    logger.info("="*50)
    
    # Запускаем бота
    try:
        logger.info("🔄 Начинаю опрос сервера Telegram...")
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("🔄 Останавливаю планировщик...")
        try:
            from .services.scheduler import stop_scheduler
            await stop_scheduler()
            logger.info("   ✅ Планировщик остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки планировщика: {e}")
        
        logger.info("🔄 Закрываю сессию бота...")
        await bot.session.close()
        logger.info("✅ Бот завершил работу")

if __name__ == "__main__":
    # Проверяем версию Python
    import platform
    python_version = platform.python_version()
    logger.info(f"🐍 Python {python_version}")
    
    # Запускаем главную функцию
    asyncio.run(main())