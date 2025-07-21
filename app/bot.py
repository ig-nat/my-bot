# bot.py
import asyncio
import logging
import sys
import platform
import os
from aiogram import Bot, Dispatcher
from app.handlers import router  # импортируем роутер из handlers.py
from app.config import TOKEN, GROUP_ID, ADMINS
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

import app.keyboards as kb

# Определяем путь к файлу лога в зависимости от операционной системы
def get_log_path():
    if platform.system() == "Windows":
        # Для Windows - в папке проекта
        return "bot.log"
    else:
        # Для Linux/Synology NAS
        nas_path = "/volume2/RussOutdoor/bot.log"
        # Проверяем, существует ли директория NAS
        if os.path.exists("/volume2/RussOutdoor/"):
            return nas_path
        else:
            # Если нет, используем локальный путь
            return "bot.log"

LOG_FILE_PATH = get_log_path()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
    ]
)

# Переводим сообщения логгера на русский язык
logging._levelToName = {
    logging.CRITICAL: 'КРИТИЧЕСКАЯ ОШИБКА',
    logging.ERROR: 'ОШИБКА',
    logging.WARNING: 'ПРЕДУПРЕЖДЕНИЕ',
    logging.INFO: 'ИНФО',
    logging.DEBUG: 'ОТЛАДКА',
    logging.NOTSET: 'НЕ ЗАДАНО',
}

# Отключаем подробные логи aiogram
logging.getLogger('aiogram.event').setLevel(logging.WARNING)
logging.getLogger('aiogram.dispatcher').setLevel(logging.WARNING)
logging.getLogger('aiogram.bot.api').setLevel(logging.WARNING)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def set_group_commands(bot):
    """Установка команд бота для групповых чатов"""
    commands = [
        BotCommand(command="refresh", description="Обновить заявки"),
        BotCommand(command="admin", description="Команды администратора"),
        BotCommand(command="cleanup", description="Очистить хранилище от старых заявок"),
        BotCommand(command="reset_user", description="Сбросить состояние пользователя"),
        BotCommand(command="reset_all", description="Сбросить состояние всех пользователей")
    ]
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllGroupChats()
    )

async def send_admin_panel(bot):
    """Отправляет админ-панель в группу"""
    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text="👨‍💼 Бот запущен. Панель администратора доступна.",
            reply_markup=kb.admin_kb
        )
        logger.info(f"Админ-панель отправлена в группу {GROUP_ID}")
    except Exception as e:
        logger.error(f"Не удалось отправить админ-панель в группу: {str(e)}")

async def on_startup(bot):
    """Действия при запуске бота"""
    logger.info(f"🚀 Бот запущен на {platform.system()} и готов к работе")
    logger.info(f"📄 Файл лога: {LOG_FILE_PATH}")

async def on_shutdown(bot, dp):
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    
    # Закрываем сессию бота
    if hasattr(bot, 'session') and bot.session is not None:
        await bot.session.close()
        logger.info("Сессия бота закрыта")
    
    # Отменяем все задачи, кроме текущей
    try:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        # Ждем завершения всех задач
        if tasks:
            logger.info(f"Ожидание завершения {len(tasks)} задач...")
            await asyncio.gather(*tasks, return_exceptions=True)
    except RuntimeError:
        # Если нет запущенного event loop
        pass
    
    logger.info("✅ Бот полностью остановлен")


async def create_redis_storage():
    """Создание Redis хранилища с fallback на Memory"""
    try:
        # Используем redis.asyncio вместо aioredis
        import redis.asyncio as redis
        redis_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
        await redis_client.ping()  # Проверяем соединение
        logger.info("✅ Redis подключен успешно")
        return RedisStorage(redis=redis_client)
    except Exception as e:
        logger.warning(f"⚠️ Redis недоступен ({str(e)}), используем MemoryStorage")
        return MemoryStorage()



async def main():
    """Основная функция запуска бота"""
    # Инициализация хранилища состояний
# Инициализация хранилища состояний
    storage = await create_redis_storage()
    
    # Инициализация бота с токеном из конфигурации
    bot = Bot(token=TOKEN)
    
    try:
        # Инициализация диспетчера для обработки сообщений
        dp = Dispatcher(storage=storage)
        
        # Подключение роутера с обработчиками сообщений
        dp.include_router(router)
        
        # Установка команд бота для групповых чатов
        await set_group_commands(bot)
        
        # Выполняем действия при запуске
        await on_startup(bot)
        
        # Отправляем админ-панель в группу регистраторов
        await send_admin_panel(bot)
        
        # Запуск бота в режиме polling (постоянное ожидание новых сообщений)
        logger.info("📡 Запуск поллинга...")
        await dp.start_polling(bot)
    finally:
        # Выполняем действия при остановке
        await on_shutdown(bot, dp)

if __name__ == '__main__':
    try:
        # Запуск асинхронной функции main
        asyncio.run(main())
    except KeyboardInterrupt:
        # Обработка прерывания работы бота (например, Ctrl+C)
        logger.info('🛑 Бот выключен пользователем')
    except Exception as e:
        # Логирование ошибок, если они возникнут
        logger.error(f"💥 Произошла ошибка: {e}", exc_info=True)
