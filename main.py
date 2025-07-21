# main.py
import asyncio
import logging
import sys
import platform
import os
from app.bot import main

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

if __name__ == '__main__':
    try:
        logger.info(f"🎯 Запуск главного процесса бота на {platform.system()}")
        logger.info(f"📄 Файл лога: {LOG_FILE_PATH}")
        # Запуск асинхронной функции main()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
    finally:
        # В Windows может не быть запущенного event loop в этой точке
        try:
            # Закрываем все незакрытые ресурсы
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                logger.info(f"⏳ Ожидание завершения {len(tasks)} задач...")
                # Отменяем все задачи
                for task in tasks:
                    task.cancel()
                
                # Ждем завершения всех задач
                loop = asyncio.get_event_loop()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        except RuntimeError:
            # Если нет запущенного event loop
            pass
        except Exception as e:
            logger.error(f"💥 Ошибка при завершении задач: {e}")
        
        logger.info("✅ Бот полностью остановлен")
