# это тут
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, InputMediaPhoto, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from app.database import db
from aiogram.filters import Command
from app.redis_client import redis_client
import datetime




import os
import uuid
from app.utils import save_photo_file

import app.keyboards as kb
from app.config import GROUP_ID, GROUP_ID_2, GROUP_ID_3, ADMINS, TOKEN
from aiogram.fsm.storage.base import StorageKey
import logging
import time
import asyncio
from aiogram.exceptions import TelegramRetryAfter

import datetime
import sqlite3
from collections import defaultdict
import aiogram.exceptions
import json  # ← ДОБАВИТЬ ЭТУ СТРОКУ
from io import BytesIO  # ← И ЭТУ СТРОКУ

router = Router()
logger = logging.getLogger(__name__)
storage = {}


def restore_storage_smart():
    """Умное восстановление: Redis → БД → синхронизация"""
    try:
        # 1. Пробуем Redis
        redis_data = {}
        if redis_client is not None:
            try:
                redis_data = redis_client.get_all_active_requests()
                logger.info(f"📡 Получено {len(redis_data)} заявок из Redis")
            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {str(e)}")
        else:
            logger.info("📡 Redis не настроен")
        
        # 2. Получаем данные из БД
        db_data = {}
        try:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT request_id, user_id, user_name, address, request_type, gid, is_accepted 
                    FROM requests 
                    WHERE status != 'completed'
                    ORDER BY created_at DESC
                ''')
                
                for row in cursor.fetchall():
                    request_id, user_id, user_name, address, request_type, gid, is_accepted = row
                    db_data[int(request_id)] = {
                        "user_id": user_id,
                        "user_name": user_name,
                        "adres": address,
                        "request_type": request_type or "regular",
                        "gid": gid or "",
                        "is_accepted": bool(is_accepted),
                        "is_completed": False,
                        "source": "database"
                    }
            
            logger.info(f"💾 Получено {len(db_data)} заявок из БД")
        except Exception as e:
            logger.error(f"Ошибка чтения БД: {str(e)}")
        
        # 3. Объединяем данные (Redis приоритетнее для активных операций)
        storage.clear()
        storage.update(db_data)      # Сначала БД (базовые данные)
        
        # Обновляем Redis данными (они могут быть более свежими)
        for req_id, req_data in redis_data.items():
            if req_id in storage:
                # Объединяем данные: БД + Redis
                storage[req_id].update(req_data)
                storage[req_id]["source"] = "redis+database"
            else:
                # Только в Redis (возможно новая заявка)
                storage[req_id] = req_data
                storage[req_id]["source"] = "redis"
        
        logger.info(f"🔄 Восстановлено {len(storage)} заявок (Redis: {len(redis_data)}, БД: {len(db_data)})")
        
        # 4. Синхронизируем Redis с актуальными данными
        if redis_client is not None and storage:
            try:
                # Сохраняем только активные заявки в Redis
                active_requests = {k: v for k, v in storage.items() if not v.get("is_completed", False)}
                redis_client.save_all_active_requests(active_requests)
                logger.info(f"📡 Redis синхронизирован ({len(active_requests)} активных заявок)")
            except Exception as e:
                logger.warning(f"Не удалось синхронизировать Redis: {str(e)}")
        
    except Exception as e:
        logger.error(f"Ошибка умного восстановления: {str(e)}")

# Вызываем умное восстановление при импорте модуля
restore_storage_smart()


def sync_storage_to_both(request_id, request_data):
    """Синхронизация заявки в Redis И БД"""
    try:
        # 1. Обновляем в Redis (быстро)
        if redis_client is not None:
            try:
                redis_client.save_request(str(request_id), request_data)
                logger.debug(f"📡 Заявка {request_id} синхронизирована в Redis")
            except Exception as e:
                logger.warning(f"Не удалось сохранить заявку {request_id} в Redis: {str(e)}")
        
        # 2. Обновляем в БД (надежно) - если данные полные
        if request_data.get("user_id") and request_data.get("user_name"):
            try:
                # Сохраняем базовую информацию
                db.save_request(
                    request_id=str(request_id),
                    user_id=request_data.get("user_id"),
                    user_name=request_data.get("user_name"),
                    address=request_data.get("adres", ""),
                    request_type=request_data.get("request_type", "regular")
                )
                
                # Обновляем GiD если есть
                if request_data.get("gid"):
                    db.update_request_gid(str(request_id), request_data.get("gid"))
                
                # Обновляем статус если завершена
                if request_data.get("is_completed"):
                    db.update_request_status(str(request_id), "completed", "system")
                
                logger.debug(f"💾 Заявка {request_id} синхронизирована в БД")
            except Exception as e:
                logger.warning(f"Не удалось сохранить заявку {request_id} в БД: {str(e)}")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации заявки {request_id}: {str(e)}")


def sync_storage_to_both(request_id, request_data):
    """Синхронизация заявки в Redis И БД"""
    try:
        # 1. Обновляем в Redis (быстро)
        if redis_client is not None:
            try:
                redis_client.save_request(str(request_id), request_data)
                logger.debug(f"📡 Заявка {request_id} синхронизирована в Redis")
            except Exception as e:
                logger.warning(f"Не удалось сохранить заявку {request_id} в Redis: {str(e)}")
        
        # 2. Обновляем в БД (надежно) - если данные полные
        if request_data.get("user_id") and request_data.get("user_name"):
            try:
                # Сохраняем базовую информацию
                db.save_request(
                    request_id=str(request_id),
                    user_id=request_data.get("user_id"),
                    user_name=request_data.get("user_name"),
                    address=request_data.get("adres", ""),
                    request_type=request_data.get("request_type", "regular")
                )
                
                # Обновляем GiD если есть
                if request_data.get("gid"):
                    db.update_request_gid(str(request_id), request_data.get("gid"))
                
                # Обновляем статус если завершена
                if request_data.get("is_completed"):
                    db.update_request_status(str(request_id), "completed", "system")
                
                logger.debug(f"💾 Заявка {request_id} синхронизирована в БД")
            except Exception as e:
                logger.warning(f"Не удалось сохранить заявку {request_id} в БД: {str(e)}")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации заявки {request_id}: {str(e)}")

def log_user_action(user_id: int, user_name: str, action: str, details: str = ""):
    """Централизованное логирование действий пользователей"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] 👤 {user_name} (ID: {user_id}) - {action}"
    if details:
        log_message += f" | {details}"
    
    logger.info(log_message)
    
    # Можно также сохранять в отдельный файл
    try:
        with open("user_actions.log", "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception as e:
        logger.warning(f"Не удалось записать в user_actions.log: {str(e)}")



async def cleanup_completed_requests():
    """Очищает завершённые заявки из storage"""
    completed_requests = []
    current_time = datetime.datetime.now()
    
    for req_id, req_data in list(storage.items()):
        if req_data.get("is_completed", False):
            # Проверяем, что заявка завершена более 30 минут назад
            completed_at = req_data.get("completed_at")
            if completed_at and (current_time - completed_at).total_seconds() > 1800:  # 30 минут
                completed_requests.append(req_id)
    
    for req_id in completed_requests:
        del storage[req_id]
    
    if completed_requests:
        logger.info(f"Очищено завершённых заявок из storage: {len(completed_requests)}")



# Добавим улучшенную функцию для отправки сообщений с обработкой ограничений
async def send_message_with_retry(bot, chat_id, text, **kwargs):
    """Отправка сообщения с обработкой ошибок и повторными попытками"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            if "retry after" in str(e).lower():
                retry_after = int(str(e).split("retry after")[1].split()[0].strip())
                logger.warning(f"Превышен лимит запросов, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after + 0.5)
            else:
                logger.error(f"Ошибка отправки сообщения: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)


async def safe_delete_message(bot, chat_id, message_id):
    """Безопасное удаление сообщения с обработкой ошибок"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        if "message to delete not found" in str(e).lower():
            # Сообщение уже удалено, это не ошибка
            return False
        logger.warning(f"Не удалось удалить сообщение {message_id}: {str(e)}")
        return False



# Аналогично для отправки медиа-группы
async def safe_send_media_group(bot, chat_id, media, **kwargs):
    """Отправка медиа-группы с обработкой ошибок и повторными попытками"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await bot.send_media_group(chat_id=chat_id, media=media, **kwargs)
        except Exception as e:
            if "retry after" in str(e).lower():
                retry_after = int(str(e).split("retry after")[1].split()[0].strip())
                logger.warning(f"Превышен лимит запросов, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after + 0.5)
            else:
                logger.error(f"Ошибка отправки медиа-группы: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)

# Добавьте эту функцию в начало файла handlers.py после импортов и определения router





class Reg(StatesGroup):
    city = State()      # ← НОВЫЙ ШАГ
    adres = State()     # ← ОСТАЕТСЯ
    photo = State()
    photo2 = State()
    photo3 = State()
    final_photo = State()


class Moderator1State(StatesGroup):
    waiting_for_gid = State()
    waiting_for_reason = State()


class Moderator2State(StatesGroup):
    waiting_for_final_approval = State()
    waiting_for_reject_reason = State()

# В начале файла, где определены другие классы состояний
class AdminState(StatesGroup):
    waiting_for_username = State()

class CancelRegistrationState(StatesGroup):
    waiting_for_reason = State()
# Добавить после существующих классов состояний (после class CancelRegistrationState)
class OpsReplacement(StatesGroup):
    city = State()      # ← НОВОЕ ПОЛЕ
    adres = State()
    ops_photo = State()
    screen_photo = State()
    final_photo = State()

class TvReplacement(StatesGroup):
    city = State()      # ← НОВОЕ ПОЛЕ
    adres = State()
    tv_photo = State()
    final_photo = State()

class StatsState(StatesGroup):
    waiting_for_start_date = State()
    waiting_for_end_date = State()

async def safe_delete_message(bot, chat_id: int, message_id: int) -> bool:
    """Безопасное удаление сообщения"""
    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "message to delete not found" in error_msg:
            logger.debug(f"Сообщение {message_id} уже удалено")
        elif "message can't be deleted" in error_msg:
            logger.debug(f"Сообщение {message_id} нельзя удалить (возможно, слишком старое)")
        elif "bad request" in error_msg:
            logger.debug(f"Некорректный запрос на удаление сообщения {message_id}: {str(e)}")
        else:
            logger.warning(f"Неожиданная ошибка при удалении сообщения {message_id}: {str(e)}")
        return False

async def safe_edit_reply_markup(bot, chat_id: int, message_id: int, new_markup: InlineKeyboardMarkup) -> bool:
    """Безопасное редактирование клавиатуры"""
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_markup
        )
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "message is not modified" in error_msg:
            logger.debug("Клавиатура уже имеет нужное состояние")
            return True
        elif "message to edit not found" in error_msg:
            logger.debug(f"Сообщение {message_id} для редактирования не найдено")
            return False
        elif "message can't be edited" in error_msg:
            logger.debug(f"Сообщение {message_id} нельзя редактировать (возможно, слишком старое)")
            return False
        elif "bad request" in error_msg:
            logger.debug(f"Некорректный запрос на редактирование сообщения {message_id}: {str(e)}")
            return False
        else:
            logger.warning(f"Неожиданная ошибка при редактировании клавиатуры: {str(e)}")
            return False



# Добавьте эту функцию для управления задержками между запросами
async def with_rate_limit(func, *args, **kwargs):
    """Выполняет функцию с ограничением частоты запросов"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if "retry after" in str(e).lower():
                retry_after = int(str(e).split("retry after")[1].split()[0].strip())
                logger.warning(f"Превышен лимит запросов, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after + 1)  # Добавляем 1 секунду для надежности
            else:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)




@router.message(Command("refresh"))
async def refresh_requests(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return

    try:
        # Фильтруем только активные (незавершенные) заявки
        active_requests = {}
        for req_id, req_data in storage.items():
            if isinstance(req_data, dict) and not req_data.get("is_completed", False):
                active_requests[req_id] = req_data

        if not active_requests:
            await message.answer("ℹ️ Нет активных заявок для обновления")
            return

        await message.answer(f"🔄 Начинаю обновление {len(active_requests)} заявок...")

        # Удаляем старые сообщения
        for request_id, request_data in active_requests.items():
            try:
                if "button_message_id" in request_data:
                    await safe_delete_message(
                        message.bot,
                        chat_id=GROUP_ID,
                        message_id=request_data["button_message_id"]
                    )
                if "media_group_ids" in request_data:
                    for msg_id in request_data["media_group_ids"]:
                        await safe_delete_message(
                            message.bot,
                            chat_id=GROUP_ID,
                            message_id=msg_id
                        )
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Ошибка при удалении сообщения: {str(e)}")

        # Отправляем заявки заново
        updated_count = 0
        for request_id, request_data in list(active_requests.items()):
            try:
                if "media" not in request_data:
                    logger.warning(f"Заявка {request_id} не содержит медиа-данных")
                    continue

                adres = request_data.get("adres", "")
                user_name = request_data.get("user_name", "Неизвестный")
                
                if adres:
                    await send_message_with_retry(
                        message.bot,
                        chat_id=GROUP_ID,
                        text=f"Отправитель: {user_name}\nАдрес: {adres}"
                    )
                    await asyncio.sleep(0.5)

                sent_messages = await safe_send_media_group(
                    message.bot,
                    GROUP_ID,
                    media=request_data["media"]
                )

                media_group_ids = [msg.message_id for msg in sent_messages]

                keyboard = kb.moderator_full
                if request_data.get("is_accepted", False):
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(text="——— ПРОБЛЕМЫ СО СВЯЗЬЮ ———", callback_data="ignore")
                            ],
                            [
                                InlineKeyboardButton(text="🔴 НЕТ СВЯЗИ", callback_data="no_connection"),
                                InlineKeyboardButton(text="⚠️ ПЛОХАЯ СВЯЗЬ", callback_data="bad_connection")
                            ],
                            [
                                InlineKeyboardButton(text="🔄 СМЕНА ПОРТА", callback_data="change_port"),
                                InlineKeyboardButton(text="🔌 ПЕРЕЗАГРУЗИ ТВ", callback_data="restart_tv")
                            ]
                        ]
                    )

                await asyncio.sleep(0.5)

                button_message = await send_message_with_retry(
                    message.bot,
                    GROUP_ID,
                    f"Принять заявку от {user_name}:",
                    reply_markup=keyboard,
                    reply_to_message_id=media_group_ids[0]
                )

                # ИСПРАВЛЕНИЕ: Обновляем БД с новым request_id
                old_request_id = str(request_id)
                new_request_id = str(media_group_ids[0])
                
                # Обновляем request_id в базе данных
                try:
                    with sqlite3.connect(db.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE requests 
                            SET request_id = ? 
                            WHERE request_id = ?
                        ''', (new_request_id, old_request_id))
                        conn.commit()
                        logger.info(f"БД обновлена: {old_request_id} -> {new_request_id}")
                except Exception as e:
                    logger.error(f"Ошибка обновления БД: {str(e)}")

                # Обновляем информацию о заявке в хранилище
                new_request_data = {
                    **request_data,
                    "button_message_id": button_message.message_id,
                    "media_group_ids": media_group_ids
                }
                
                if adres:
                    new_request_data["adres"] = adres
                if user_name:
                    new_request_data["user_name"] = user_name
                
                # Сохраняем обновленную заявку с новым ID
                storage[media_group_ids[0]] = new_request_data
                
                # Обновляем состояние пользователя
                if "user_id" in request_data:
                    user_id = request_data["user_id"]
                    try:
                        user_state = FSMContext(
                            storage=state.storage,
                            key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=message.bot.id)
                        )
                        
                        current_state = await user_state.get_state()
                        if current_state == Reg.final_photo.state:
                            user_data = await user_state.get_data()
                            
                            user_data_updated = {}
                            for k, v in user_data.items():
                                if k not in ['group_message_id', 'adres']:
                                    user_data_updated[k] = v
                            
                            user_data_updated['group_message_id'] = media_group_ids[0]
                            if adres:
                                user_data_updated['adres'] = adres
                                
                            await user_state.update_data(**user_data_updated)
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении состояния пользователя {user_id}: {str(e)}")
                
                # Удаляем старую запись
                if request_id != media_group_ids[0]:
                    del storage[request_id]

                updated_count += 1
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Ошибка при переотправке заявки {request_id}: {str(e)}")
                await asyncio.sleep(1)

        await send_message_with_retry(
            message.bot,
            chat_id=message.chat.id,
            text=f"✅ Обновлено заявок: {updated_count} из {len(active_requests)}"
        )

    except Exception as e:
        logger.error(f"Ошибка в /refresh: {str(e)}")
        try:
            await send_message_with_retry(
                message.bot,
                chat_id=message.chat.id,
                text="❌ Ошибка при обновлении заявок"
            )
        except Exception as e2:
            logger.error(f"Не удалось отправить сообщение об ошибке: {str(e2)}")








# Добавляем команду для вызова админ-панели
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    await message.answer("👨‍💼 Панель администратора", reply_markup=kb.admin_kb)


@router.message(Command("storage_info"))
async def storage_info(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    # Получаем тип хранилища из state
    storage_type = type(state.storage).__name__
    
    if "Redis" in storage_type:
        status = "✅ Redis активен - состояния сохраняются при перезагрузке"
        try:
            # Дополнительная проверка Redis
            if hasattr(state.storage, 'redis'):
                redis_info = await state.storage.redis.info()
                uptime = redis_info.get('uptime_in_seconds', 0)
                status += f"\n⏱️ Redis работает: {uptime} секунд"
        except Exception as e:
            status += f"\n⚠️ Проблемы с подключением к Redis: {str(e)}"
    else:
        status = "⚠️ Memory Storage - состояния НЕ сохраняются при перезагрузке"
    
    await message.answer(f"🗄️ Тип хранилища: {storage_type}\n{status}")



# Обработчик для кнопки "Вернуться"
@router.message(F.text == "🔙 Вернуться")
async def back_to_main(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    await message.answer("Вы вернулись в главное меню", reply_markup=kb.main)

# Обработчик для кнопки "Статистика"
# Добавить в обработчик статистики более детальную информацию
@router.message(F.text == "📊 Статистика")
async def show_statistics_menu(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    await message.answer("📊 Выберите период для статистики:", reply_markup=kb.stats_period_kb)

@router.callback_query(F.data == "stats_today")
async def show_stats_today(callback: CallbackQuery):
    try:
        stats = db.get_statistics_today()
        
        if not stats:
            await callback.message.edit_text("❌ Нет данных за сегодня")
            return
        
        today = datetime.date.today().strftime("%d.%m.%Y")
        message_text = f"📊 **СТАТИСТИКА ЗА СЕГОДНЯ ({today})**\n\n"
        message_text += f"📝 **Общие показатели:**\n"
        message_text += f"• Всего заявок: {stats['total']}\n"
        message_text += f"• ✅ Завершено: {stats['completed']}\n"
        message_text += f"• ⏳ В процессе: {stats['pending']}\n\n"
        
        message_text += f"🔧 **По типам работ:**\n"
        message_text += f"• 📺 Регистрация экранов: {stats['regular']}\n"
        message_text += f"• 🔧 Замена OPS: {stats['ops']}\n"
        message_text += f"• 📺 Замена телевизоров: {stats['tv']}\n\n"
        
        if stats['users']:
            message_text += "👥 **По пользователям:**\n"
            for user_data in stats['users']:
                user_name, total, completed, regular, ops, tv = user_data
                message_text += f"• {user_name}: {total} всего (✅{completed}) "
                message_text += f"[📺{regular} 🔧{ops} 📺{tv}]\n"
        
        await callback.message.edit_text(message_text, reply_markup=None)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики за сегодня: {str(e)}")
        await callback.answer("❌ Ошибка при получении статистики")

@router.callback_query(F.data == "stats_all_time")
async def show_stats_all_time(callback: CallbackQuery):
    try:
        stats = db.get_statistics_all_time()
        
        if not stats:
            await callback.message.edit_text("❌ Нет данных")
            return
        
        message_text = f"📊 **СТАТИСТИКА ЗА ВСЕ ВРЕМЯ**\n\n"
        message_text += f"📝 **Общие показатели:**\n"
        message_text += f"• Всего заявок: {stats['total']}\n"
        message_text += f"• ✅ Завершено: {stats['completed']}\n"
        message_text += f"• ⏳ В процессе: {stats['pending']}\n\n"
        
        message_text += f"🔧 **По типам работ:**\n"
        message_text += f"• 📺 Регистрация экранов: {stats['regular']}\n"
        message_text += f"• 🔧 Замена OPS: {stats['ops']}\n"
        message_text += f"• 📺 Замена телевизоров: {stats['tv']}\n\n"
        
        if stats['users']:
            message_text += "👥 **По пользователям:**\n"
            for user_data in stats['users']:
                user_name, total, completed, regular, ops, tv = user_data
                message_text += f"• {user_name}: {total} всего (✅{completed}) "
                message_text += f"[📺{regular} 🔧{ops} 📺{tv}]\n"
        
        await callback.message.edit_text(message_text, reply_markup=None)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики за все время: {str(e)}")
        await callback.answer("❌ Ошибка при получении статистики")

@router.callback_query(F.data == "stats_custom_period")
async def start_custom_period(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StatsState.waiting_for_start_date)
    await callback.message.edit_text(
        "📅 Введите дату начала периода в формате ДД.ММ.ГГГГ\n"
        "Например: 01.01.2025"
    )
    await callback.answer()

@router.message(StatsState.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    try:
        start_date = datetime.datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(start_date=start_date)
        await state.set_state(StatsState.waiting_for_end_date)
        await message.answer(
            f"✅ Дата начала: {start_date.strftime('%d.%m.%Y')}\n\n"
            "📅 Теперь введите дату окончания периода в формате ДД.ММ.ГГГГ\n"
            "Например: 31.01.2025"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")

@router.message(StatsState.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    try:
        end_date = datetime.datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        data = await state.get_data()
        start_date = data.get('start_date')
        
        if end_date < start_date:
            await message.answer("❌ Дата окончания не может быть раньше даты начала")
            return
        
        # Получаем статистику за период
        stats = db.get_statistics_period(start_date, end_date)
        
        if not stats:
            await message.answer("❌ Нет данных за указанный период")
            await state.clear()
            return
        
        message_text = f"📊 **СТАТИСТИКА ЗА ПЕРИОД**\n"
        message_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        message_text += f"📝 **Общие показатели:**\n"
        message_text += f"• Всего заявок: {stats['total']}\n"
        message_text += f"• ✅ Завершено: {stats['completed']}\n"
        message_text += f"• ⏳ В процессе: {stats['pending']}\n\n"
        
        message_text += f"🔧 **По типам работ:**\n"
        message_text += f"• 📺 Регистрация экранов: {stats['regular']}\n"
        message_text += f"• 🔧 Замена OPS: {stats['ops']}\n"
        message_text += f"• 📺 Замена телевизоров: {stats['tv']}\n\n"
        
        if stats['users']:
            message_text += "👥 **По пользователям:**\n"
            for user_data in stats['users']:
                user_name, total, completed, regular, ops, tv = user_data
                message_text += f"• {user_name}: {total} всего (✅{completed}) "
                message_text += f"[📺{regular} 🔧{ops} 📺{tv}]\n"
        
        await message.answer(message_text, reply_markup=kb.admin_kb)
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    except Exception as e:
        logger.error(f"Ошибка при обработке периода: {str(e)}")
        await message.answer("❌ Ошибка при получении статистики")
        await state.clear()

# Команда для сброса состояния конкретного пользователя
@router.message(Command("reset_user"))
async def reset_user_state(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Получаем имя пользователя из аргументов команды
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Укажите имя пользователя: /reset_user <имя>")
            return
        
        user_name = args[1].strip()
        
        # Ищем пользователя по имени
        user_found = False
        for req_id, req_data in list(storage.items()):
            if req_data.get("user_name") == user_name and not req_data.get("is_completed", False):
                user_id = req_data.get("user_id")
                if user_id:
                    # Сбрасываем состояние пользователя
                    user_state = FSMContext(
                        storage=message.bot.fsm.storage,
                        key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=message.bot.id)
                    )
                    await user_state.clear()
                    
                    # Отправляем сообщение пользователю
                    await message.bot.send_message(
                        chat_id=user_id,
                        text="🔄 Ваша текущая регистрация была сброшена администратором. Вы можете начать заново.",
                        reply_markup=kb.main
                    )
                    
                    # Помечаем заявку как завершенную
                    req_data["is_completed"] = True
                    req_data["completed_at"] = datetime.datetime.now()
                    req_data["completed_by"] = "admin_reset"
                    
                    user_found = True
        
        if user_found:
            await message.answer(f"✅ Состояние пользователя {user_name} успешно сброшено")
        else:
            await message.answer(f"❌ Пользователь {user_name} не найден или у него нет активных заявок")
    
    except Exception as e:
        logger.error(f"Ошибка при сбросе состояния пользователя: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при сбросе состояния пользователя")

# Команда для сброса состояния всех пользователей
@router.message(Command("reset_all"))
async def reset_all_states(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Запрашиваем подтверждение
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить все", callback_data="confirm_reset_all"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reset_all")
            ]
        ])
        
        await message.answer(
            "⚠️ Вы уверены, что хотите сбросить состояние ВСЕХ пользователей?\n"
            "Это действие нельзя отменить!",
            reply_markup=confirm_kb
        )
    
    except Exception as e:
        logger.error(f"Ошибка при запросе подтверждения сброса: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при запросе подтверждения")

# Обработчики для подтверждения/отмены сброса всех состояний
@router.callback_query(F.data == "confirm_reset_all")
async def confirm_reset_all(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return
    
    try:
        reset_count = 0
        
        # Сбрасываем состояние всех пользователей с активными заявками
        for req_id, req_data in list(storage.items()):
            if not req_data.get("is_completed", False):
                user_id = req_data.get("user_id")
                if user_id:
                    # Сбрасываем состояние пользователя
                    user_state = FSMContext(
                        storage=state.storage,  # Используем storage из текущего state
                        key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=callback.bot.id)
                    )
                    await user_state.clear()
                    
                    # Отправляем сообщение пользователю
                    try:
                        await callback.bot.send_message(
                            chat_id=user_id,
                            text="🔄 Ваша текущая регистрация была сброшена администратором. Вы можете начать заново.",
                            reply_markup=kb.main
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {str(e)}")
                    
                    # Помечаем заявку как завершенную
                    req_data["is_completed"] = True
                    req_data["completed_at"] = datetime.datetime.now()
                    req_data["completed_by"] = "admin_reset_all"
                    
                    reset_count += 1
        
        await callback.message.edit_text(
            f"✅ Сброшено состояний: {reset_count}",
            reply_markup=None
        )
        
        # Отправляем новое сообщение с админской клавиатурой
        await callback.message.answer("Операция завершена", reply_markup=kb.admin_kb)
        
        await callback.answer("✅ Все состояния сброшены")
    
    except Exception as e:
        logger.error(f"Ошибка при сбросе всех состояний: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при сбросе состояний")
        await callback.message.edit_text(
            "❌ Произошла ошибка при сбросе состояний",
            reply_markup=None
        )
        # Отправляем новое сообщение с админской клавиатурой
        await callback.message.answer("Вернуться в админ-панель", reply_markup=kb.admin_kb)


@router.callback_query(F.data == "cancel_reset_all")
async def cancel_reset_all(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return
    
    await callback.message.edit_text(
        "❌ Сброс всех состояний отменен",
        reply_markup=None
    )
    
    await callback.answer("✅ Операция отменена")


# Обработчик для кнопки "Обновить заявки" (аналог /refresh)
@router.message(F.text == "🔄 Обновить заявки")
async def refresh_button(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    # Используем существующую функцию refresh_requests, передавая state
    await refresh_requests(message, state)


@router.message(F.text == 'регистрация экрана')
async def start_registration(message: Message, state: FSMContext):
    logger.info(f"👤 Пользователь {message.from_user.full_name} (ID: {message.from_user.id}) начал регистрацию")
    await state.set_state(Reg.city)  # ← ИЗМЕНИЛИ: было Reg.adres
    await message.answer("🏙️ Укажите город:", reply_markup=kb.cancel_kb)  # ← ИЗМЕНИЛИ: было "адрес"

# НОВЫЙ: Обработчик города для обычной регистрации
@router.message(Reg.city)
async def save_city(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        logger.info(f"❌ Пользователь {message.from_user.full_name} отменил регистрацию на этапе ввода города")
        await state.clear()
        await message.answer("❎ Регистрация отменена", reply_markup=kb.main)
        return

    logger.info(f"🏙️ Пользователь {message.from_user.full_name} ввел город: {message.text}")
    await state.update_data(city=message.text)
    await state.set_state(Reg.adres)  # ← ПЕРЕХОДИМ К АДРЕСУ
    await message.answer("✅ Город сохранён! Теперь введите адрес ПВЗ:", reply_markup=kb.cancel_kb)


@router.message(F.text == 'замена оборудования')
async def start_replacement(message: Message, state: FSMContext):
    # Добавь эту строку
    if message.chat.type != 'private':
        return

    logger.info(f"👤 Пользователь {message.from_user.full_name} (ID: {message.from_user.id}) начал замену оборудования")
    await message.answer("🔧 Выберите тип замены:", reply_markup=kb.replacement_type_kb)

@router.message(F.text == 'замена OPS')
async def start_ops_replacement(message: Message, state: FSMContext):
    logger.info(f"👤 Пользователь {message.from_user.full_name} выбрал замену OPS")
    await state.set_state(OpsReplacement.city)  # ← ИЗМЕНИЛИ: было OpsReplacement.adres
    await message.answer("🏙️ Укажите город:", reply_markup=kb.cancel_kb)  # ← ИЗМЕНИЛИ: было "адрес"


# НОВЫЙ: Обработчик города для замены OPS
@router.message(OpsReplacement.city)
async def save_ops_city(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    logger.info(f"🏙️ Пользователь {message.from_user.full_name} ввел город для замены OPS: {message.text}")
    await state.update_data(city=message.text)
    await state.set_state(OpsReplacement.adres)  # ← ПЕРЕХОДИМ К АДРЕСУ
    await message.answer("✅ Город сохранён! Теперь введите адрес ремонта:", reply_markup=kb.cancel_kb)


@router.message(F.text == 'замена Телевизора')
async def start_tv_replacement(message: Message, state: FSMContext):
    logger.info(f"👤 Пользователь {message.from_user.full_name} выбрал замену телевизора")
    await state.set_state(TvReplacement.city)  # ← ИЗМЕНИЛИ: было TvReplacement.adres
    await message.answer("🏙️ Укажите город:", reply_markup=kb.cancel_kb)  # ← ИЗМЕНИЛИ: было "адрес"


# НОВЫЙ: Обработчик города для замены TV
@router.message(TvReplacement.city)
async def save_tv_city(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    logger.info(f"🏙️ Пользователь {message.from_user.full_name} ввел город для замены TV: {message.text}")
    await state.update_data(city=message.text)
    await state.set_state(TvReplacement.adres)  # ← ПЕРЕХОДИМ К АДРЕСУ
    await message.answer("✅ Город сохранён! Теперь введите адрес ремонта:", reply_markup=kb.cancel_kb)


# Обработчики для замены OPS
@router.message(OpsReplacement.adres)
async def save_ops_adres(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        logger.info(f"❌ Пользователь {message.from_user.full_name} отменил замену OPS на этапе ввода адреса")
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    logger.info(f"📍 Пользователь {message.from_user.full_name} ввел адрес для замены OPS: {message.text}")
    await state.update_data(adres=message.text)
    await state.set_state(OpsReplacement.ops_photo)
    await message.answer("✅ Адрес сохранён! Отправьте фото серийного номера OPS", reply_markup=kb.cancel_kb)

@router.message(OpsReplacement.ops_photo)
async def save_ops_photo(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        await state.update_data(ops_photo=message.photo[-1].file_id)
        await state.set_state(OpsReplacement.screen_photo)
        await message.answer("📸 Фото серийного номера OPS принято! Теперь отправьте фото СИРЕНЕВОГО экрана", reply_markup=kb.cancel_kb)
    else:
        await message.answer("📸 Пожалуйста, отправьте фото серийного номера OPS.")

@router.message(OpsReplacement.screen_photo)
async def save_ops_screen_photo(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        try:
            data = await state.get_data()
            ops_photo = data.get('ops_photo')
            screen_photo = message.photo[-1].file_id
            adres = data.get('adres')

            if None in (ops_photo, screen_photo, adres):
                raise ValueError("Не все данные получены")

            user_name = message.from_user.full_name

            # Отправляем информацию о заявке с пометкой ЗАМЕНА OPS
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID,
                text=f"🔧 **ЗАМЕНА OPS** 🔧\nОтправитель: {user_name}\nАдрес: {adres}",
                reply_markup=ReplyKeyboardRemove()
            )

            media = [
                InputMediaPhoto(media=ops_photo, caption=f"🔧 ЗАМЕНА OPS - Серийник OPS от {user_name}"),
                InputMediaPhoto(media=screen_photo, caption=f"🔧 ЗАМЕНА OPS - Фото экрана от {user_name}")
            ]

            sent_messages = await safe_send_media_group(message.bot, GROUP_ID, media)
            media_group_ids = [msg.message_id for msg in sent_messages]

            button_message = await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID,
                text=f"🔧 ЗАМЕНА OPS - Принять заявку от {user_name}:",
                reply_markup=kb.moderator_full,
                reply_to_message_id=media_group_ids[0]
            )

            # Сохраняем информацию о заявке с пометкой типа замены
            storage[media_group_ids[0]] = {
                "user_id": message.from_user.id,
                "user_name": user_name,
                "button_message_id": button_message.message_id,
                "is_accepted": False,
                "media": media,
                "media_group_ids": media_group_ids,
                "adres": adres,
                "replacement_type": "OPS"  # Добавляем тип замены
            }

            if redis_client is not None:
                redis_client.save_request(str(media_group_ids[0]), storage[media_group_ids[0]])
            else:
                logger.debug("Redis недоступен, заявка не сохранена в Redis")
            # Сохраняем в базу данных
            db.save_request(
                request_id=str(media_group_ids[0]),
                user_id=message.from_user.id,
                user_name=user_name,
                address=adres,
                request_type="OPS"
            )

            db.save_request(
                request_id=str(media_group_ids[0]),
                user_id=message.from_user.id,
                user_name=user_name,
                address=adres,
                request_type="regular"
            )

            await message.answer("✅ Заявка на замену OPS отправлена, ожидайте.", reply_markup=ReplyKeyboardRemove())
            await state.update_data(group_message_id=media_group_ids[0])
            await state.set_state(OpsReplacement.final_photo)

            logger.info(f"📝 Заявка на замену OPS от {user_name} создана с адресом: {adres}")

        except Exception as e:
            logger.error(f"Ошибка при отправке данных замены OPS: {str(e)}", exc_info=True)
            await message.answer("❌ Ошибка! Начните заново.", reply_markup=kb.main)
            await state.clear()
    else:
        await message.answer("📸 Пожалуйста, отправьте фото СИРЕНЕВОГО экрана.")

# Обработчики для замены телевизора
@router.message(TvReplacement.adres)
async def save_tv_adres(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        logger.info(f"❌ Пользователь {message.from_user.full_name} отменил замену телевизора на этапе ввода адреса")
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    logger.info(f"📍 Пользователь {message.from_user.full_name} ввел адрес для замены телевизора: {message.text}")
    await state.update_data(adres=message.text)
    await state.set_state(TvReplacement.tv_photo)
    await message.answer("✅ Адрес сохранён! Отправьте фото серийного номера телевизора", reply_markup=kb.cancel_kb)



@router.message(TvReplacement.tv_photo)
async def save_tv_photo(message: Message, state: FSMContext):
    logger.info(f"🔧 Пользователь {message.from_user.full_name} отправил фото для замены ТВ")
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Замена оборудования отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        logger.info(f"📸 Получено фото от {message.from_user.full_name}")
        
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        try:
            data = await state.get_data()
            logger.info(f"🔍 Данные состояния: {data}")
            
            tv_photo = message.photo[-1].file_id
            adres = data.get('adres')
            city = data.get('city', '')  # Получаем город если есть
            user_name = message.from_user.full_name

            if not adres:
                raise ValueError("Адрес не получен")

            # Формируем полный адрес
            full_address = f"{city}, {adres}" if city else adres

            # Отправляем сразу в GROUP_ID_2 (минуя GROUP_ID)
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID_2,
                text=f"📺 **ЗАМЕНА ТЕЛЕВИЗОРА** 📺\nОтправитель: {user_name}\nАдрес: {full_address}"
            )

            # Отправляем фото серийного номера телевизора
            sent_message = await message.bot.send_photo(
                chat_id=GROUP_ID_2,
                photo=tv_photo,
                caption=f"📺 ЗАМЕНА ТЕЛЕВИЗОРА - Серийник ТВ от {user_name}"
            )

            # Сохраняем информацию о заявке
            storage[sent_message.message_id] = {
                "user_id": message.from_user.id,
                "user_name": user_name,
                "is_accepted": True,  # Сразу принята
                "adres": adres,
                "city": city,
                "replacement_type": "TV",
                "is_completed": False
            }  # ← ДОБАВЬ ЭТУ ЗАКРЫВАЮЩУЮ СКОБКУ!
            
            # Синхронизируем с Redis и БД
            try:
                sync_storage_to_both(sent_message.message_id, storage[sent_message.message_id])
            except Exception as e:
                logger.warning(f"Ошибка синхронизации замены ТВ: {str(e)}")
            
            # Сохраняем в базу данных
            db.save_request(
                request_id=str(sent_message.message_id),
                user_id=message.from_user.id,
                user_name=user_name,
                address=full_address,
                request_type="TV"
            )

            # Сразу переходим к финальному фото
            await message.answer(
                "✅ Фото серийного номера телевизора отправлено! Теперь дождитесь появления рекламных роликов и отправьте финальное фото. На финальном фото должна быть стойка менеджера и экран с рекламой",
                reply_markup=kb.cancel_kb
            )
            
            await state.update_data(group_message_id=sent_message.message_id)
            await state.set_state(TvReplacement.final_photo)

            logger.info(f"📝 Заявка на замену телевизора от {user_name} отправлена в GROUP_ID_2 с адресом: {full_address}")

        except Exception as e:
            logger.error(f"Ошибка при отправке данных замены телевизора: {str(e)}", exc_info=True)
            await message.answer("❌ Ошибка! Начните заново.", reply_markup=kb.main)
            await state.clear()
    else:
        await message.answer("📸 Пожалуйста, отправьте фото серийного номера телевизора.")



# Обработчик финального фото для замены OPS
@router.message(OpsReplacement.final_photo)
async def ops_final_step(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        if data.get("final_photo_sent", False):
            await message.answer("⏳ Вы уже отправили финальное фото. Ожидайте решения модератора.")
            return

        if message.content_type != ContentType.PHOTO:
            await message.answer("Пожалуйста, отправьте фото.")
            return

        group_message_id = data.get("group_message_id")
        adres = data.get("adres")

        if not group_message_id or not adres:
            raise ValueError("ID сообщения в группе или адрес отсутствует")

        if group_message_id not in storage:
            await message.answer("⚠️ Ваша заявка не найдена в системе. Пожалуйста, начните замену заново.")
            await state.clear()
            return
            
        # ИСПРАВЛЕНИЕ: Получаем storage_data ПЕРЕД использованием
        storage_data = storage.get(group_message_id)
        if not storage_data or not storage_data.get("is_accepted", False):
            await message.answer("⏳ Заявка еще не одобрена. Ожидайте!")
            return

        # Теперь можно безопасно использовать storage_data
        city = storage_data.get("city", "Город не указан")
        gid = storage_data.get("gid", "GiD не указан")
        
        # ... остальной код функции ...


        
        
        photo_id = message.photo[-1].file_id
        user_name = message.from_user.full_name
        
        info_text = f"🔧 **ЗАМЕНА OPS** - Финальное фото от {user_name}\nАдрес: {adres}\nGiD: {gid}"
        
        try:
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID_3,
                text=info_text
            )
            
            await asyncio.sleep(0.5)
            
            sent_message = await message.bot.send_photo(
                chat_id=GROUP_ID_3,
                photo=photo_id,
                caption=f"🔧 ЗАМЕНА OPS - Финальное фото от {user_name}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке финального фото замены OPS: {str(e)}")
            await message.answer("❌ Ошибка отправки фото. Попробуйте еще раз.")
            return

        accept_button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Принять", callback_data=f"accept_final:{sent_message.message_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"reject_final:{sent_message.message_id}")
        ]])

        await asyncio.sleep(0.5)

        await send_message_with_retry(
            message.bot,
            chat_id=GROUP_ID_3,
            text=f"🔧 ЗАМЕНА OPS - Заявка от {user_name} на рассмотрении:",
            reply_markup=accept_button,
            reply_to_message_id=sent_message.message_id
        )

        storage[sent_message.message_id] = {
            "user_id": message.from_user.id,
            "group_message_id": group_message_id,
            "is_accepted": True,
            "user_name": user_name,
            "adres": adres,
            "gid": gid,
            "replacement_type": "OPS"
        }

        await state.update_data(final_photo_sent=True, final_message_id=sent_message.message_id)
        await message.answer("✅ Финальное фото замены OPS отправлено на модерацию. Ожидайте решения.")

        logger.info(f"📸 Финальное фото замены OPS от {user_name} отправлено с адресом: {adres}, GiD: {gid}")

    except Exception as e:
        logger.error(f"Ошибка при отправке финального фото замены OPS: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка отправки. Попробуйте еще раз.")

# Обработчик финального фото для замены телевизора
@router.message(TvReplacement.final_photo)
async def tv_final_step(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        if data.get("final_photo_sent", False):
            await message.answer("⏳ Вы уже отправили финальное фото. Ожидайте решения модератора.")
            return

        if message.content_type != ContentType.PHOTO:
            await message.answer("Пожалуйста, отправьте фото.")
            return

        group_message_id = data.get("group_message_id")
        adres = data.get("adres")
        storage_data = storage.get(group_message_id)
        if not storage_data:
            await message.answer("⚠️ Заявка не найдена")
            return

        city = storage_data.get("city", "Город не указан")

        if not group_message_id or not adres:
            raise ValueError("ID сообщения в группе или адрес отсутствует")

        if group_message_id not in storage:
            await message.answer("⚠️ Ваша заявка не найдена в системе. Пожалуйста, начните замену заново.")
            await state.clear()
            return

        photo_id = message.photo[-1].file_id
        user_name = message.from_user.full_name
        
        info_text = f"📺 **ЗАМЕНА ТЕЛЕВИЗОРА** - Финальное фото от {user_name}\nАдрес: {adres}"
        
        try:
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID_3,
                text=info_text
            )
            
            await asyncio.sleep(0.5)
            
            sent_message = await message.bot.send_photo(
                chat_id=GROUP_ID_3,
                photo=photo_id,
                caption=f"📺 ЗАМЕНА ТЕЛЕВИЗОРА - Финальное фото от {user_name}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке финального фото замены телевизора: {str(e)}")
            await message.answer("❌ Ошибка отправки фото. Попробуйте еще раз.")
            return

        accept_button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Принять", callback_data=f"accept_final:{sent_message.message_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"reject_final:{sent_message.message_id}")
        ]])

        await asyncio.sleep(0.5)

        await send_message_with_retry(
            message.bot,
            chat_id=GROUP_ID_3,
            text=f"📺 ЗАМЕНА ТЕЛЕВИЗОРА - Заявка от {user_name} на рассмотрении:",
            reply_markup=accept_button,
            reply_to_message_id=sent_message.message_id
        )

        storage[sent_message.message_id] = {
            "user_id": message.from_user.id,
            "group_message_id": group_message_id,
            "is_accepted": True,
            "user_name": user_name,
            "adres": adres,
            "replacement_type": "TV"
        }

        await state.update_data(final_photo_sent=True, final_message_id=sent_message.message_id)
        await message.answer("✅ Финальное фото замены телевизора отправлено на модерацию. Ожидайте решения.")

        logger.info(f"📸 Финальное фото замены телевизора от {user_name} отправлено с адресом: {adres}")

    except Exception as e:
        logger.error(f"Ошибка при отправке финального фото замены телевизора: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка отправки. Попробуйте еще раз.")




@router.message(Reg.adres)
async def save_adres(message: Message, state: FSMContext):
    # Добавь эту строку в самое начало
    if message.chat.type != 'private':
        return
    if message.text == "❌ Отмена":
        logger.info(f"❌ Пользователь {message.from_user.full_name} отменил регистрацию на этапе ввода адреса")
        await state.clear()
        await message.answer("❎ Регистрация отменена", reply_markup=kb.main)
        return

    logger.info(f"📍 Пользователь {message.from_user.full_name} ввел адрес: {message.text}")
    await state.update_data(adres=message.text)
    await state.set_state(Reg.photo)
    await message.answer("✅ Адрес сохранён! Далее отправьте фото СИРЕНЕВОГО экрана", reply_markup=kb.cancel_kb)


@router.message(Reg.photo)
async def save_adres(message: Message, state: FSMContext):
    if message.chat.type != 'private':
        return

    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Регистрация отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        # Проверяем, что отправлено только одно фото
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        try:
            # Сохраняем фото в папку
            photo = message.photo[-1]
            file = await message.bot.get_file(photo.file_id)
            file_bytes = BytesIO()
            await message.bot.download_file(file.file_path, destination=file_bytes)
            file_bytes.seek(0)
            data = file_bytes.read()
            saved_path = save_photo_file(data)
            
            # Сохраняем file_id для отправки в группу И путь к файлу
            await state.update_data(photo=message.photo[-1].file_id, photo_path=saved_path)
            await state.set_state(Reg.photo2)
            await message.answer("📸 Фото принято! Теперь фото наклейки с серийным номером телевизора", reply_markup=kb.cancel_kb)
            
            logger.info(f"📸 Первое фото сохранено: {saved_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении первого фото: {str(e)}", exc_info=True)
            await message.answer("❌ Ошибка при сохранении фото. Попробуйте ещё раз.")
    else:
        await message.answer("📸 Пожалуйста, фото СИРЕНЕВОГО экрана.")



@router.message(Reg.photo2)
async def save_adres(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Регистрация отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        # Проверяем, что отправлено только одно фото
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        try:
            # Сохраняем фото в папку
            photo = message.photo[-1]
            file = await message.bot.get_file(photo.file_id)
            file_bytes = BytesIO()
            await message.bot.download_file(file.file_path, destination=file_bytes)
            file_bytes.seek(0)
            data = file_bytes.read()
            saved_path = save_photo_file(data)
            
            # Сохраняем file_id для отправки в группу И путь к файлу
            await state.update_data(photo2=message.photo[-1].file_id, photo2_path=saved_path)
            await state.set_state(Reg.photo3)
            await message.answer("📸 Фото принято! Теперь фото наклейки с серийным номером компьютера (ОПС)", reply_markup=kb.cancel_kb)
            
            logger.info(f"📸 Второе фото сохранено: {saved_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении второго фото: {str(e)}", exc_info=True)
            await message.answer("❌ Ошибка при сохранении фото. Попробуйте ещё раз.")
    else:
        await message.answer("📸 Пожалуйста, фото наклейки с серийным номером телевизора.")



@router.message(Reg.photo3)
async def save_photo3(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❎ Регистрация отменена", reply_markup=kb.main)
        return

    if message.content_type == ContentType.PHOTO:
        # Проверяем, что отправлено только одно фото
        if hasattr(message, 'media_group_id') and message.media_group_id:
            await message.answer("📸 Пожалуйста, отправляйте фотографии по одной, а не группой.")
            return
        
        try:
            data = await state.get_data()
            photo = data.get('photo')
            photo2 = data.get('photo2')
            photo3 = message.photo[-1].file_id
            adres = data.get('adres')
            city = data.get('city')  # ← ДОБАВИЛИ ГОРОД

            if None in (photo, photo2, photo3, adres, city):  # ← ПРОВЕРЯЕМ ГОРОД
                raise ValueError("Не все данные получены")

            user_name = message.from_user.full_name

            # Отправляем информацию о заявке с городом
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID,
                text=f"Отправитель: {user_name}\n🏙️ Город: {city}\nАдрес: {adres}",  # ← ДОБАВИЛИ ГОРОД
                reply_markup=ReplyKeyboardRemove()
            )

            media = [
                InputMediaPhoto(media=photo, caption=f"Фото экрана от {user_name}"),
                InputMediaPhoto(media=photo2, caption=f"Серийник ТВ от {user_name}"),
                InputMediaPhoto(media=photo3, caption=f"Серийник ПК от {user_name}")
            ]

            # Используем безопасную отправку медиа-группы
            sent_messages = await safe_send_media_group(message.bot, GROUP_ID, media)
            media_group_ids = [msg.message_id for msg in sent_messages]

            # Отправляем сообщение с кнопками
            button_message = await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID,
                text=f"Принять заявку от {user_name}:",
                reply_markup=kb.moderator_full,
                reply_to_message_id=media_group_ids[0]
            )

            # Сохраняем информацию о заявке с адресом И городом
            storage[media_group_ids[0]] = {
                "user_id": message.from_user.id,
                "user_name": user_name,
                "button_message_id": button_message.message_id,
                "is_accepted": False,
                "media": media,
                "media_group_ids": media_group_ids,
                "adres": adres,
                "city": city  # ← ДОБАВИЛИ ГОРОД В STORAGE
            }
            
            # Синхронизируем с Redis и БД
            try:
                sync_storage_to_both(media_group_ids[0], storage[media_group_ids[0]])
            except Exception as e:
                logger.warning(f"Ошибка синхронизации: {str(e)}")
            
            # Дополнительно сохраняем в Redis (если доступен)
            if redis_client is not None:
                try:
                    redis_client.save_request(str(media_group_ids[0]), storage[media_group_ids[0]])
                except Exception as e:
                    logger.warning(f"Ошибка сохранения в Redis: {str(e)}")
            else:
                logger.debug("Redis недоступен, заявка не сохранена в Redis")

            # Сохраняем в базу данных
            db.save_request(
                request_id=str(media_group_ids[0]),
                user_id=message.from_user.id,
                user_name=user_name,
                address=f"{city}, {adres}",  # ← ГОРОД + АДРЕС В БД
                request_type="regular"
            )

            await message.answer(
                "✅ заявка отправлена, ожидайте.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.update_data(group_message_id=media_group_ids[0])
            await state.set_state(Reg.final_photo)

            # Добавляем логирование с городом
            logger.info(f"📝 Заявка от {user_name} создана с городом: {city}, адресом: {adres}")

        except Exception as e:
            logger.error(f"Ошибка при отправке данных: {str(e)}", exc_info=True)
            await message.answer("❌ Ошибка! Начните заново.", reply_markup=kb.main)
            await state.clear()
    else:
        await message.answer("📸 Пожалуйста, отправьте фото серийного номера компьютера.")




@router.message(F.text == "⏳ Ожидание проверки")
async def waiting_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == Reg.final_photo.state:
        await message.answer("⏳ Ваша заявка находится на рассмотрении. Пожалуйста, ожидайте.")
    else:
        await message.answer("⚠️ У вас нет активных заявок на рассмотрении.", reply_markup=kb.main)
        await state.clear()




# Обработчик для групповых чатов - игнорирует команды меню
@router.message(F.text.in_(['регистрация экрана', 'замена оборудования', 'замена OPS', 'замена Телевизора']))
async def ignore_menu_in_groups(message: Message):
    if message.chat.type != 'private':
        return

    # Просто игнорируем эти сообщения в группах
    pass





# Обработчик для кнопки "Сбросить пользователя"
@router.message(F.text == "🔁 Сбросить пользователя")
async def reset_user_button(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    # Создаем состояние для ввода имени пользователя
    class AdminState(StatesGroup):
        waiting_for_username = State()
    
    await state.set_state(AdminState.waiting_for_username)
    await message.answer("👤 Введите имя пользователя, состояние которого нужно сбросить:")

# Обработчик для получения имени пользователя
@router.message(AdminState.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    user_name = message.text.strip()
    
    try:
        # Ищем пользователя по имени
        user_found = False
        for req_id, req_data in list(storage.items()):
            if req_data.get("user_name") == user_name and not req_data.get("is_completed", False):
                user_id = req_data.get("user_id")
                if user_id:
                    # Сбрасываем состояние пользователя
                    user_state = FSMContext(
                        storage=state.storage,  # Используем storage из текущего state
                        key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=message.bot.id)
                    )
                    await user_state.clear()
                    
                    # Отправляем сообщение пользователю
                    await message.bot.send_message(
                        chat_id=user_id,
                        text="🔄 Ваша текущая регистрация была сброшена администратором. Вы можете начать заново.",
                        reply_markup=kb.main
                    )
                    
                    # Помечаем заявку как завершенную
                    req_data["is_completed"] = True
                    req_data["completed_at"] = datetime.datetime.now()
                    req_data["completed_by"] = "admin_reset"
                    
                    user_found = True
        
        if user_found:
            await message.answer(f"✅ Состояние пользователя {user_name} успешно сброшено", reply_markup=kb.admin_kb)
        else:
            await message.answer(f"❌ Пользователь {user_name} не найден или у него нет активных заявок", reply_markup=kb.admin_kb)
    
    except Exception as e:
        logger.error(f"Ошибка при сбросе состояния пользователя: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при сбросе состояния пользователя", reply_markup=kb.admin_kb)
    
    await state.clear()

# Обработчик для кнопки "Сбросить всех"
@router.message(F.text == "⚠️ Сбросить всех")
async def reset_all_button(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        # Запрашиваем подтверждение
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить все", callback_data="confirm_reset_all"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reset_all")
            ]
        ])
        
        await message.answer(
            "⚠️ Вы уверены, что хотите сбросить состояние ВСЕХ пользователей?\n"
            "Это действие нельзя отменить!",
            reply_markup=confirm_kb
        )
    
    except Exception as e:
        logger.error(f"Ошибка при запросе подтверждения сброса: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при запросе подтверждения", reply_markup=kb.admin_kb)


@router.callback_query(F.data == "confirm_reset_all")
async def confirm_reset_all(callback: CallbackQuery, state: FSMContext):  # Добавляем параметр state
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return
    
    try:
        reset_count = 0
        
        # Сбрасываем состояние всех пользователей с активными заявками
        for req_id, req_data in list(storage.items()):
            if not req_data.get("is_completed", False):
                user_id = req_data.get("user_id")
                if user_id:
                    # Сбрасываем состояние пользователя
                    user_state = FSMContext(
                        storage=state.storage,  # Используем storage из текущего state
                        key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=callback.bot.id)
                    )
                    await user_state.clear()
                    
                    # Отправляем сообщение пользователю
                    try:
                        await callback.bot.send_message(
                            chat_id=user_id,
                            text="🔄 Ваша текущая регистрация была сброшена администратором. Вы можете начать заново.",
                            reply_markup=kb.main
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {str(e)}")
                    
                    # Помечаем заявку как завершенную
                    req_data["is_completed"] = True
                    req_data["completed_at"] = datetime.datetime.now()
                    req_data["completed_by"] = "admin_reset_all"
                    
                    reset_count += 1
        
        await callback.message.edit_text(
            f"✅ Сброшено состояний: {reset_count}",
            reply_markup=None
        )
        
        # Отправляем новое сообщение с админской клавиатурой
        await callback.message.answer("Операция завершена", reply_markup=kb.admin_kb)
        
        await callback.answer("✅ Все состояния сброшены")
    
    except Exception as e:
        logger.error(f"Ошибка при сбросе всех состояний: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при сбросе состояний")
        await callback.message.edit_text(
            "❌ Произошла ошибка при сбросе состояний",
            reply_markup=None
        )
        # Отправляем новое сообщение с админской клавиатурой
        await callback.message.answer("Вернуться в админ-панель", reply_markup=kb.admin_kb)

@router.callback_query(F.data == "cancel_reset_all")
async def cancel_reset_all(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return
    
    await callback.message.edit_text(
        "❌ Сброс всех состояний отменен",
        reply_markup=None
    )
    
    # Отправляем новое сообщение с админской клавиатурой
    await callback.message.answer("Вернуться в админ-панель", reply_markup=kb.admin_kb)
    
    await callback.answer("✅ Операция отменена")


@router.message(F.text == "📄 Экспорт данных")
async def export_button(message: Message):
    if message.from_user.id not in ADMINS:
        return
    # Используем функцию экспорта
    await export_data(message)

@router.message(F.text == "🧹 Очистка хранилища")
async def cleanup_button(message: Message):
    if message.from_user.id not in ADMINS:
        return
    # Используем существующую функцию cleanup_storage
    await cleanup_storage(message)



@router.callback_query(F.data == "cancel_registration")
async def cancel_registration(callback: CallbackQuery, state: FSMContext):
    try:
        group_message_id = callback.message.reply_to_message.message_id

        if group_message_id not in storage:
            raise KeyError("Заявка не найдена")

        user_id = storage[group_message_id]["user_id"]
        await state.update_data(group_message_id=group_message_id, user_id=user_id)

        try:
            await callback.bot.delete_message(
                chat_id=GROUP_ID,
                message_id=storage[group_message_id]["button_message_id"]
            )
        except Exception as e:
            logger.warning(f"Сообщение с кнопкой уже удалено или не найдено: {str(e)}")

        # Устанавливаем состояние ожидания причины отмены
        await state.set_state(CancelRegistrationState.waiting_for_reason)
        await callback.message.answer("📝 Укажите причину отмены регистрации:")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при отмене регистрации: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при отмене регистрации.")

@router.message(CancelRegistrationState.waiting_for_reason)
async def handle_cancel_reason(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        group_message_id = data.get("group_message_id")
        user_id = data.get("user_id")
        if not group_message_id or not user_id:
            raise ValueError("Не удалось получить данные из состояния")
        
        # Удаляем сообщения заявки из группы
        if group_message_id in storage:
            try:
                # Удаляем медиа-группу
                for msg_id in storage[group_message_id].get("media_group_ids", []):
                    try:
                        await message.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                    except Exception as e:
                        logger.warning(f"Сообщение {msg_id} уже удалено или не найдено: {str(e)}")
                
                # Удаляем сообщение с кнопками
                button_message_id = storage[group_message_id].get("button_message_id")
                if button_message_id:
                    try:
                        await message.bot.delete_message(chat_id=GROUP_ID, message_id=button_message_id)
                    except Exception as e:
                        logger.warning(f"Сообщение с кнопкой уже удалено или не найдено: {str(e)}")
            except Exception as e:
                logger.warning(f"Ошибка при удалении сообщений: {str(e)}")
        
        # Сбрасываем состояние пользователя
        user_state = FSMContext(
            storage=state.storage,
            key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=message.bot.id)
        )
        await user_state.clear()
        
        # Отправляем сообщение пользователю
        await message.bot.send_message(
            chat_id=user_id,
            text=f"❌ Ваша заявка отменена. Причина: {message.text}",
            reply_markup=kb.main
        )
        
        # Помечаем заявку как завершенную
        if group_message_id in storage:
            storage[group_message_id]["is_completed"] = True
            storage[group_message_id]["cancel_reason"] = message.text
        
        await message.answer("✅ Причина отправлена пользователю. Заявка отменена.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обработке причины отмены: {str(e)}", exc_info=True)
        await message.answer("❌ Не флуди! мешаешь работать")
        await state.clear()



@router.message(F.chat.id == GROUP_ID, Moderator1State.waiting_for_gid)
async def handle_gid(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        group_message_id = data.get("group_message_id")
        if not group_message_id:
            raise ValueError("Не удалось получить ID сообщения из состояния")
            
        if group_message_id not in storage:
            await message.answer("❌ Заявка не найдена в системе")
            await state.clear()
            return
            
        storage_data = storage.get(group_message_id)
        media = storage_data.get("media")
        user_name = storage_data.get("user_name", "Неизвестный")
        replacement_type = storage_data.get("replacement_type", "")
        
        # Получаем адрес из данных заявки
        address = storage_data.get("adres", "Адрес не указан")
        city = storage_data.get("city", "Город не указан")  # ← ДОБАВЬ ЭТУ СТРОКУ

        if media:
            try:
                # Формируем текст с пометкой типа замены
                info_text = f"Отправитель: {user_name}\nАдрес: {address}"
                # И обнови отправку:
                info_text = f"Отправитель: {user_name}\n🏙️ Город: {city}\nАдрес: {address}"  # ← ОБНОВИ
                if replacement_type == "OPS":
                    info_text = f"🔧 **ЗАМЕНА OPS** 🔧\n{info_text}"
                
                # Отправляем информацию о заявке в группу инженеров
                await send_message_with_retry(
                    message.bot,
                    chat_id=GROUP_ID_2,
                    text=info_text
                )
                
                # Отправляем медиа-группу в группу инженеров
                sent_messages_group2 = await safe_send_media_group(message.bot, GROUP_ID_2, media)
                
                # Отправляем GiD отдельным сообщением
                gid_text = f"GiD: {message.text}"
                if replacement_type == "OPS":
                    gid_text = f"🔧 ЗАМЕНА OPS - {gid_text}"
                
                await send_message_with_retry(
                    message.bot,
                    chat_id=GROUP_ID_2,
                    text=gid_text,
                    reply_to_message_id=sent_messages_group2[0].message_id
                )
                
                logger.info(f"📤 Заявка от {user_name} отправлена инженерам с адресом: {address}, GiD: {message.text}, тип: {replacement_type or 'обычная регистрация'}")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке медиа в GROUP_ID_2: {str(e)}")
                await message.answer("❌ Ошибка отправки данных инженерам. Попробуйте еще раз.")
                return
        
        # Отправляем GiD в основную группу
        main_gid_text = f"GiD: {message.text}"
        if replacement_type == "OPS":
            main_gid_text = f"🔧 ЗАМЕНА OPS - {main_gid_text}"
            
        await send_message_with_retry(
            message.bot,
            chat_id=GROUP_ID,
            text=main_gid_text,
            reply_to_message_id=group_message_id
        )
        
        # Обновляем статус заявки
        storage[group_message_id]["is_accepted"] = True
        storage[group_message_id]["gid"] = message.text
        # Синхронизируем изменения
        sync_storage_to_both(group_message_id, storage[group_message_id])

        if redis_client is not None:
            redis_client.update_request(str(group_message_id), {

        "is_accepted": True,
        "gid": message.text
    })
        storage[group_message_id]["gid"] = message.text
        
        db.update_request_gid(str(group_message_id), message.text)
        user_id = storage[group_message_id]["user_id"]
        
        # Уведомляем пользователя
        user_message = "✅ Заявка одобрена! Теперь дождитесь появления рекламных роликов и отправьте финальное фото. На финальном фото должна быть стойка менеджера и экран с рекламой"
        if replacement_type == "OPS":
            user_message = "✅ Заявка на замену OPS одобрена! " + user_message
        
        await send_message_with_retry(
            message.bot,
            chat_id=user_id,
            text=user_message,
            reply_markup=kb.cancel_kb
        )
        
        # Обновляем клавиатуру
        connection_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Копировать адрес", callback_data="copy_address")
        ],
        [
            InlineKeyboardButton(text="——— ПРОБЛЕМЫ СО СВЯЗЬЮ ———", callback_data="ignore")
        ],
        [
            InlineKeyboardButton(text="🔴 НЕТ СВЯЗИ", callback_data="no_connection"),
            InlineKeyboardButton(text="⚠️ ПЛОХАЯ СВЯЗЬ", callback_data="bad_connection")
        ],
        [
            InlineKeyboardButton(text="🔄 СМЕНА ПОРТА", callback_data="change_port"),
            InlineKeyboardButton(text="🔌 ПЕРЕЗАГРУЗИ ТВ", callback_data="restart_tv")
        ],
        [
            InlineKeyboardButton(text="💬 СВЯЗЬ С МОНТАЖНИКОМ", callback_data="contact_user")
        ]
    ]
)


        
        try:
            button_message_id = storage_data.get("button_message_id")
            if button_message_id:
                success = await safe_edit_reply_markup(
                    message.bot,
                    GROUP_ID,
                    button_message_id,
                    connection_buttons
                )
                if not success:
                    logger.warning("Не удалось обновить клавиатуру - сообщение могло быть удалено")
        except Exception as e:
            logger.warning(f"Не удалось обновить клавиатуру: {str(e)}")
            
        await message.answer("✅ GiD и адрес отправлены в группу к инженерам.")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке GiD: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка отправки GiD. Попробуйте еще раз.")
        await state.clear()






@router.callback_query(F.data == "accept_registration")
async def accept_registration(callback: CallbackQuery, state: FSMContext):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return
            
        data = storage[group_message_id]
        
        try:
            # Обновляем клавиатуру, оставляя только кнопки проблем со связью
            connection_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="——— ПРОБЛЕМЫ СО СВЯЗЬЮ ———", callback_data="ignore")
        ],
        [
            InlineKeyboardButton(text="🔴 НЕТ СВЯЗИ", callback_data="no_connection"),
            InlineKeyboardButton(text="⚠️ ПЛОХАЯ СВЯЗЬ", callback_data="bad_connection")
        ],
        [
            InlineKeyboardButton(text="🔄 СМЕНА ПОРТА", callback_data="change_port"),
            InlineKeyboardButton(text="🔌 ПЕРЕЗАГРУЗИ ТВ", callback_data="restart_tv")
        ],
        [
            InlineKeyboardButton(text="💬 СВЯЗЬ С МОНТАЖНИКОМ", callback_data="contact_user")
        ]
    ]
)

            
            # Используем безопасное редактирование клавиатуры
            success = await safe_edit_reply_markup(
                callback.bot,
                GROUP_ID,
                data["button_message_id"],
                connection_buttons
            )
            
            if not success:
                logger.warning("Не удалось обновить клавиатуру")
        except Exception as e:
            logger.warning(f"Не удалось обновить клавиатуру: {str(e)}")
        
        # Используем функцию с повторными попытками для отправки сообщения пользователю
        await send_message_with_retry(
            callback.bot,
            chat_id=data["user_id"],
            text="✅ Заявка принята! Ожидайте подтверждения.",
            reply_markup=kb.cancel_kb
        )
        
        # Отправляем сообщение в группу с повторными попытками
        await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"✅ Принял: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )
        
        # Запрашиваем GiD
        await callback.message.answer("📝 Введи GiD:")
        await state.set_state(Moderator1State.waiting_for_gid)
        await state.update_data(group_message_id=group_message_id)
        
    except Exception as e:
        logger.error(f"Ошибка при принятии заявки: {str(e)}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при обработке заявки")


@router.message(Reg.final_photo)
async def final_step(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        if data.get("final_photo_sent", False):
            await message.answer("⏳ Вы уже отправили финальное фото. Ожидайте решения модератора.")
            return

        if message.content_type != ContentType.PHOTO:
            await message.answer("Пожалуйста, отправьте фото.")
            return

        group_message_id = data.get("group_message_id")
        adres = data.get("adres")
        city = data.get("city", "Город не указан")  # ← ПРАВИЛЬНО: из data, а не storage_data

        if not group_message_id or not adres:
            raise ValueError("ID сообщения в группе или адрес отсутствует")

        # Проверяем наличие заявки в хранилище и её статус
        if group_message_id not in storage:
            await message.answer("⚠️ Ваша заявка не найдена в системе. Пожалуйста, начните регистрацию заново.")
            await state.clear()
            return
            
        storage_data = storage.get(group_message_id)  # ← ВОТ ГДЕ ОПРЕДЕЛЯЕТСЯ storage_data
        if not storage_data or not storage_data.get("is_accepted", False):
            await message.answer("⏳ Заявка еще не одобрена. Ожидайте! ")
            return

        # Получаем GiD из данных заявки
        gid = storage_data.get("gid", "GiD не указан")
        
        photo_id = message.photo[-1].file_id
        user_name = message.from_user.full_name
        
        # Отправляем информацию о финальной заявке С ГОРОДОМ
        info_text = f"Финальное фото от {user_name}\n🏙️ Город: {city}\nАдрес: {adres}\nGiD: {gid}"
        
        # ... остальной код без изменений


        
        try:
            # Отправляем информацию о финальной заявке
            await send_message_with_retry(
                message.bot,
                chat_id=GROUP_ID_3,
                text=info_text
            )
            
            # Добавляем небольшую задержку
            await asyncio.sleep(0.5)
            
            # Отправляем финальное фото
            sent_message = await message.bot.send_photo(
                chat_id=GROUP_ID_3,
                photo=photo_id,
                caption=f"Финальное фото от {user_name}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке финального фото: {str(e)}")
            await message.answer("❌ Ошибка отправки фото. Попробуйте еще раз.")
            return

        # Создаем кнопки для принятия/отклонения
        accept_button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Принять", callback_data=f"accept_final:{sent_message.message_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"reject_final:{sent_message.message_id}")
        ]])

        # Отправляем сообщение с кнопками, привязанное к фото
        await send_message_with_retry(
            message.bot,
            chat_id=GROUP_ID_3,
            text=f"Заявка от {user_name} на рассмотрении:",
            reply_markup=accept_button,
            reply_to_message_id=sent_message.message_id
        )

        # Сохраняем информацию о финальной заявке
        storage[sent_message.message_id] = {
            "user_id": message.from_user.id,  # ← ПРАВИЛЬНО
            "group_message_id": group_message_id,
            "is_accepted": True,
            "user_name": user_name,
            "adres": adres,
            "gid": gid
        }




        # ВАЖНО: Помечаем, что финальное фото отправлено
        await state.update_data(final_photo_sent=True, final_message_id=sent_message.message_id)
        await message.answer("✅ Финальное фото отправлено на модерацию. Ожидайте решения.")

        logger.info(f"📸 Финальное фото от {user_name} отправлено с адресом: {adres}, GiD: {gid}")

    except Exception as e:
        logger.error(f"Ошибка при отправке финального фото: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка отправки. Попробуйте еще раз.")





@router.callback_query(F.data.startswith("accept_final:"))
async def accept_final_photo(callback: CallbackQuery, state: FSMContext):
    try:
        final_message_id = int(callback.data.split(":")[1])

        if final_message_id not in storage:
            logger.warning(f"Заявка с ID {final_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        storage_data = storage.get(final_message_id)
        user_id = storage_data.get("user_id")
        
        if not user_id:
            raise ValueError("Не удалось получить user_id из хранилища")

        group_message_id = storage_data.get("group_message_id")
        user_name = storage_data.get("user_name", "Неизвестный")
        adres = storage_data.get("adres", "")
        gid = storage_data.get("gid", "")
        replacement_type = storage_data.get("replacement_type", "")
        
        # НОВОЕ: Отправляем сообщение с подписью модератора
        moderator_name = callback.from_user.full_name
        
        # Формируем текст в зависимости от типа заявки
        if replacement_type == "OPS":
            signature_text = f"🔧 ЗАМЕНА OPS - ✅ ПРИНЯТО\n"
        elif replacement_type == "TV":
            signature_text = f"📺 ЗАМЕНА ТЕЛЕВИЗОРА - ✅ ПРИНЯТО\n"
        else:
            signature_text = f"📺 РЕГИСТРАЦИЯ ЭКРАНА - ✅ ПРИНЯТО\n"
        
        signature_text += f"👤 Принял: {moderator_name}\n"
        signature_text += f"🏠 Адрес: {adres}\n"
        if gid:
            signature_text += f"🆔 GiD: {gid}\n"
        signature_text += f"📅 Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Отправляем подпись в GROUP_ID_3
        await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID_3,
            text=signature_text,
            reply_to_message_id=final_message_id
        )
        
        # Помечаем заявку как завершенную
        if redis_client is not None:
            redis_client.complete_request(str(final_message_id))
            if group_message_id:
                redis_client.complete_request(str(group_message_id))

        storage[final_message_id]["moderator_name"] = moderator_name
        db.update_request_status(
            str(final_message_id), 
            "completed", 
            moderator_name
        )

        if group_message_id and group_message_id in storage:
            storage[group_message_id]["is_completed"] = True
            storage[group_message_id]["moderator_name"] = moderator_name
            
            # Пытаемся удалить сообщение с кнопками в основной группе
            try:
                await safe_delete_message(
                    callback.bot,
                    chat_id=GROUP_ID,
                    message_id=storage[group_message_id]["button_message_id"]
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение с кнопками: {str(e)}")

        # Удаляем сообщение с кнопками принятия/отклонения
        await safe_delete_message(
            callback.bot,
            chat_id=GROUP_ID_3,
            message_id=callback.message.message_id
        )

        # Уведомляем пользователя об успешном завершении
        success_message = "🎉 Регистрация успешно завершена!"
        if replacement_type == "OPS":
            success_message = "🎉 Замена OPS успешно завершена!"
        elif replacement_type == "TV":
            success_message = "🎉 Замена телевизора успешно завершена!"
            
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text=success_message,
            reply_markup=kb.main
        )

        # Очищаем состояние пользователя
        user_state = FSMContext(
            storage=state.storage,
            key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=callback.bot.id)
        )
        await user_state.clear()

        # Логируем успешное завершение
        logger.info(f"Заявка {final_message_id} принята модератором {moderator_name}")
        
        await callback.answer("✅ Заявка принята")

    except Exception as e:
        logger.error(f"Ошибка при принятии финального фото: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при принятии заявки.")











@router.message(Command("cleanup"))
async def cleanup_storage(message: Message):
    """Очистка хранилища от старых заявок"""
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
        
    try:
        # Подсчитываем количество заявок до очистки
        total_before = len(storage)
        completed_count = sum(1 for req in storage.values() if req.get("is_completed", False))
        
        # Создаем новое хранилище только с активными заявками
        new_storage = {}
        for req_id, req_data in storage.items():
            if not req_data.get("is_completed", False):
                new_storage[req_id] = req_data
        
        # Заменяем хранилище
        storage.clear()
        storage.update(new_storage)
        
        # Подсчитываем количество заявок после очистки
        total_after = len(storage)
        removed = total_before - total_after
        
        await message.answer(
            f"🧹 Очистка хранилища завершена\n"
            f"Было заявок: {total_before}\n"
            f"Завершенных: {completed_count}\n"
            f"Удалено: {removed}\n"
            f"Осталось: {total_after}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при очистке хранилища: {str(e)}")
        await message.answer("❌ Ошибка при очистке хранилища")





# ========== КОМАНДЫ СИНХРОНИЗАЦИИ REDIS ==========

@router.message(Command("sync_force"))
async def force_sync(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        await message.answer("🔄 Начинаю принудительную синхронизацию...")
        
        # 1. Получаем данные из БД
        db_data = {}
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT request_id, user_id, user_name, address, request_type, gid, is_accepted 
                FROM requests 
                WHERE status != 'completed'
                ORDER BY created_at DESC
            ''')
            
            for row in cursor.fetchall():
                request_id, user_id, user_name, address, request_type, gid, is_accepted = row
                db_data[int(request_id)] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "adres": address,
                    "request_type": request_type or "regular",
                    "gid": gid or "",
                    "is_accepted": bool(is_accepted),
                    "is_completed": False
                }
        
        # 2. Обновляем storage
        storage.clear()
        storage.update(db_data)
        
        # 3. Синхронизируем с Redis
        redis_synced = 0
        if redis_client is not None:
            try:
                # Загружаем актуальные данные
                for req_id, req_data in storage.items():
                    redis_client.save_request(str(req_id), req_data)
                    redis_synced += 1
                    
            except Exception as e:
                await message.answer(f"⚠️ Ошибка синхронизации с Redis: {str(e)}")
        
        await message.answer(
            f"✅ **Принудительная синхронизация завершена:**\n\n"
            f"💾 Загружено из БД: {len(db_data)} заявок\n"
            f"🧠 Обновлено в Storage: {len(storage)} заявок\n"
            f"📡 Синхронизировано в Redis: {redis_synced} заявок"
        )
        
    except Exception as e:
        logger.error(f"Ошибка принудительной синхронизации: {str(e)}")
        await message.answer(f"❌ Ошибка синхронизации: {str(e)}")


@router.message(Command("redis_clear"))
async def clear_redis(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        if redis_client is None:
            await message.answer("❌ Redis не настроен")
            return
        
        # Запрашиваем подтверждение
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить Redis", callback_data="confirm_redis_clear"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_redis_clear")
            ]
        ])
        
        await message.answer(
            "⚠️ **ВНИМАНИЕ!** Вы уверены, что хотите очистить Redis?\n\n"
            "Это удалит все активные заявки из Redis (но НЕ из БД).\n"
            "После очистки используйте `/sync_force` для восстановления.",
            reply_markup=confirm_kb
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("redis_info"))
async def redis_info(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        if redis_client is None:
            await message.answer("❌ Redis не настроен")
            return
        
        # Получаем информацию о Redis
        try:
            redis_data = redis_client.get_all_active_requests()
            redis_keys = len(redis_data)
            status = "🟢 Подключен"
            
        except Exception as e:
            redis_keys = "Недоступно"
            status = f"🔴 Ошибка: {str(e)}"
        
        await message.answer(
            f"📡 **Информация о Redis:**\n\n"
            f"Статус: {status}\n"
            f"Активных заявок: {redis_keys}\n"
            f"Storage заявок: {len(storage)}\n\n"
            f"**Команды управления:**\n"
            f"• `/redis_clear` - очистить Redis\n"
            f"• `/sync_force` - принудительная синхронизация\n"
            f"• `/sync_check` - проверка синхронизации"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения информации: {str(e)}")










@router.message(Command("export"))
async def export_data(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Экспортируем данные из базы данных
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT request_id, user_id, user_name, address, request_type, 
                       gid, status, created_at, completed_at, is_accepted, moderator_name
                FROM requests
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            
            export_data_list = []
            for row in rows:
                export_item = {
                    "request_id": row[0],
                    "user_id": row[1],
                    "user_name": row[2],
                    "address": row[3],
                    "type": row[4],
                    "gid": row[5],
                    "status": row[6],
                    "created_at": row[7],
                    "completed_at": row[8],
                    "is_accepted": bool(row[9]),
                    "moderator_name": row[10]
                }
                export_data_list.append(export_item)
        
        # Создаем JSON файл
        json_data = json.dumps(export_data_list, ensure_ascii=False, indent=2)
        
        from aiogram.types import BufferedInputFile
        
        file_name = f"export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_buffer = BufferedInputFile(
            file=json_data.encode('utf-8'),
            filename=file_name
        )
        
        await message.answer_document(
            document=file_buffer,
            caption=f"📄 Экспорт данных из БД\nВсего записей: {len(export_data_list)}"
        )
        
        logger.info(f"Экспорт данных из БД выполнен администратором {message.from_user.full_name}, записей: {len(export_data_list)}")
        
    except Exception as e:
        logger.error(f"Ошибка при экспорте данных из БД: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при экспорте данных")




@router.message(Command("sync_db"))
async def sync_database(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        synced_count = 0
        
        for req_id, req_data in storage.items():
            if isinstance(req_data, dict) and req_data.get("user_id"):
                # Проверяем, есть ли уже запись в БД
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM requests WHERE request_id = ?', (str(req_id),))
                    exists = cursor.fetchone()[0] > 0
                
                if not exists:
                    # Сохраняем в БД
                    db.save_request(
                        request_id=str(req_id),
                        user_id=req_data.get("user_id"),
                        user_name=req_data.get("user_name", ""),
                        address=req_data.get("adres", ""),
                        request_type=req_data.get("replacement_type", "regular")
                    )
                    
                    # Обновляем GiD если есть
                    if req_data.get("gid"):
                        db.update_request_gid(str(req_id), req_data.get("gid"))
                    
                    # Обновляем статус если завершена
                    if req_data.get("is_completed"):
                        db.update_request_status(str(req_id), "completed", "system")
                    
                    synced_count += 1
        
        await message.answer(f"✅ Синхронизировано записей: {synced_count}")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации БД: {str(e)}")
        await message.answer("❌ Ошибка синхронизации")



@router.message(Command("sync"))
async def sync_storage_command(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Синхронизируем storage с базой данных
        db.sync_storage_to_db(storage)
        await message.answer("✅ Синхронизация завершена")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {str(e)}")
        await message.answer("❌ Ошибка синхронизации")






@router.callback_query(F.data.startswith("reject_final:"))
async def reject_final_photo(callback: CallbackQuery, state: FSMContext):
    try:
        final_message_id = int(callback.data.split(":")[1])

        if final_message_id not in storage:
            logger.warning(f"Заявка с ID {final_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        storage_data = storage.get(final_message_id)
        user_id = storage_data.get("user_id")
        
        if not user_id:
            raise ValueError("Не удалось получить user_id из хранилища")

        # НОВОЕ: Сохраняем информацию о модераторе для последующего использования
        moderator_name = callback.from_user.full_name
        storage[final_message_id]["moderator_name"] = moderator_name

        # Удаляем сообщение с кнопками
        await safe_delete_message(
            callback.bot,
            chat_id=GROUP_ID_3,
            message_id=callback.message.message_id
        )

        await state.set_state(Moderator2State.waiting_for_reject_reason)
        await state.update_data(
            final_message_id=final_message_id, 
            user_id=user_id,
            moderator_name=moderator_name  # Сохраняем имя модератора
        )

        await callback.message.answer("📝 Укажите причину отказа:")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при отклонении заявки.")



@router.message(F.chat.id == GROUP_ID_3, Moderator2State.waiting_for_reject_reason)
async def handle_reject_reason(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        final_message_id = data.get("final_message_id")
        user_id = data.get("user_id")
        moderator_name = data.get("moderator_name", message.from_user.full_name)

        if not final_message_id or not user_id:
            raise ValueError("Не удалось получить данные из состояния")

        # Получаем информацию о заявке
        storage_data = storage.get(final_message_id, {})
        user_name = storage_data.get("user_name", "Неизвестный")
        adres = storage_data.get("adres", "")
        gid = storage_data.get("gid", "")
        replacement_type = storage_data.get("replacement_type", "")

        # НОВОЕ: Отправляем сообщение с подписью модератора и причиной отказа
        # Формируем текст в зависимости от типа заявки
        if replacement_type == "OPS":
            signature_text = f"🔧 ЗАМЕНА OPS - ❌ ОТКЛОНЕНО\n"
        elif replacement_type == "TV":
            signature_text = f"📺 ЗАМЕНА ТЕЛЕВИЗОРА - ❌ ОТКЛОНЕНО\n"
        else:
            signature_text = f"📺 РЕГИСТРАЦИЯ ЭКРАНА - ❌ ОТКЛОНЕНО\n"
        
        signature_text += f"👤 Отклонил: {moderator_name}\n"
        signature_text += f"🏠 Адрес: {adres}\n"
        if gid:
            signature_text += f"🆔 GiD: {gid}\n"
        signature_text += f"📝 Причина: {message.text}\n"
        signature_text += f"📅 Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Отправляем подпись в GROUP_ID_3
        await send_message_with_retry(
            message.bot,
            chat_id=GROUP_ID_3,
            text=signature_text,
            reply_to_message_id=final_message_id
        )

        # Отправляем сообщение пользователю с причиной отказа
        reject_message = f"❌ Ваше финальное фото отклонено. Причина: {message.text}\nПожалуйста, отправьте новое финальное фото."
        
        await send_message_with_retry(
            message.bot,
            chat_id=user_id,
            text=reject_message,
            reply_markup=kb.cancel_kb
        )

        # Обновляем состояние пользователя
        user_state = FSMContext(
            storage=state.storage,
            key=StorageKey(chat_id=user_id, user_id=user_id, bot_id=message.bot.id)
        )
        await user_state.update_data(final_photo_sent=False)

        await message.answer(f"✅ Причина отказа отправлена пользователю.\nОтклонил: {moderator_name}")
        
        # Логируем отклонение
        logger.info(f"Заявка {final_message_id} отклонена модератором {moderator_name}, причина: {message.text}")
        
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка отправки причины отказа.")
        await state.clear()



@router.callback_query(F.data == "bad_connection")
async def handle_bad_connection(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_id = storage[group_message_id]["user_id"]

        # Создаем клавиатуру для проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])

        # Используем функцию с повторными попытками
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="⚠️ Связь с телевизором есть, НО не стабильна. Проверьте соединения, разъём RJ45, попробуйте сменить порт.",
            reply_markup=check_connection_kb
        )

        # Удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        status_msg = await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"⚠️ Уведомление о плохой связи отправлено пользователю.\nОтправил: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )

        # Сохраняем ID нового статусного сообщения
        storage[group_message_id]["status_messages"] = [status_msg.message_id]

        await callback.answer("✅ Пользователь уведомлен о плохой связи")

    except Exception as e:
        logger.error(f"Ошибка при обработке плохой связи: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")


@router.callback_query(F.data == "no_connection")
async def handle_no_connection(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_id = storage[group_message_id]["user_id"]

        # Создаем клавиатуру для проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])

        # Используем функцию с повторными попытками
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="❌ Отсутствует связь с телевизором. "
                 "Необходимо проверить соединения, "
                 "прозвонить витую пару LAN-тестером, "
                 "попробовать вставить провод в другой разъём на роутере",
            reply_markup=check_connection_kb
        )

        # Удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        status_msg = await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"❌ Уведомление об отсутствии связи отправлено пользователю.\nОтправил: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )

        # Сохраняем ID нового статусного сообщения
        storage[group_message_id]["status_messages"] = [status_msg.message_id]

        await callback.answer("✅ Пользователь уведомлен об отсутствии связи")

    except Exception as e:
        logger.error(f"Ошибка при обработке отсутствия связи: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data == "change_port")
async def handle_change_port(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_id = storage[group_message_id]["user_id"]

        # Создаем клавиатуру для проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])

        # Используем функцию с повторными попытками
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="🔄 Поменяй порт на роутере",
            reply_markup=check_connection_kb
        )

        # Удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        status_msg = await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"🔄 Уведомление о смене порта отправлено пользователю.\nОтправил: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )

        # Сохраняем ID нового статусного сообщения
        storage[group_message_id]["status_messages"] = [status_msg.message_id]

        await callback.answer("✅ Пользователь уведомлен о необходимости смены порта")

    except Exception as e:
        logger.error(f"Ошибка при обработке смены порта: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")




@router.callback_query(F.data == "restart_tv")
async def handle_restart_tv(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_id = storage[group_message_id]["user_id"]

        # Создаем клавиатуру для проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])

        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="🔌 Пожалуйста, перезагрузите телевизор:\n"
                 "1. Отключите телевизор от электросети на 30 секунд\n"
                 "2. Подключите телевизор к электросети и включите его",
            reply_markup=check_connection_kb
        )

        # Удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        status_msg = await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"🔌 Уведомление о перезагрузке ТВ отправлено пользователю.\nОтправил: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )

        # Сохраняем ID нового статусного сообщения
        storage[group_message_id]["status_messages"] = [status_msg.message_id]

        await callback.answer("✅ Пользователь уведомлен о необходимости перезагрузки ТВ")

    except Exception as e:
        logger.error(f"Ошибка при обработке перезагрузки ТВ: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")


@router.callback_query(F.data == "check_connection_again")
async def check_connection_again(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        # Ищем заявку этого пользователя
        user_request = None
        request_id = None
        
        for req_id, req_data in storage.items():
            if isinstance(req_data, dict) and req_data.get("user_id") == user_id and not req_data.get("is_completed", False):
                user_request = req_data
                request_id = req_id
                break
        
        if not user_request:
            await callback.answer("❌ Ваша заявка не найдена")
            return
        
        # ИСПРАВЛЕНИЕ: Проверяем, существует ли заявка в storage
        if request_id not in storage:
            await callback.answer("❌ Заявка была обновлена. Попробуйте ещё раз.")
            return
        
        # Создаем клавиатуру для результатов проверки связи
        connection_result_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ СВЯЗЬ ВОССТАНОВЛЕНА", callback_data="connection_restored"),
                InlineKeyboardButton(text="❌ СВЯЗЬ ВСЕ ЕЩЕ ПЛОХАЯ", callback_data="connection_still_bad")
            ]
        ])
        
        # ИСПРАВЛЕНИЕ: Безопасно удаляем предыдущие статусные сообщения
        if "status_messages" in storage[request_id]:
            for msg_id in storage[request_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)
        
        # Отправляем новое сообщение в группу модераторов
        try:
            # Сначала пробуем отправить с привязкой к сообщению
            status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"🔄 Пользователь {callback.from_user.full_name} выполнил рекомендации и просит проверить связь снова",
                reply_markup=connection_result_kb,
                reply_to_message_id=request_id
            )
        except Exception as e:
            # Если не получилось с привязкой, отправляем без неё
            logger.warning(f"Не удалось отправить с привязкой к сообщению {request_id}, отправляем без привязки: {str(e)}")
            status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"🔄 Пользователь {callback.from_user.full_name} выполнил рекомендации и просит проверить связь снова\n(Заявка ID: {request_id})",
                reply_markup=connection_result_kb
            )
        
        # ИСПРАВЛЕНИЕ: Безопасно сохраняем ID нового статусного сообщения
        if request_id in storage:
            storage[request_id]["status_messages"] = [status_msg.message_id]
        
        # Редактируем сообщение пользователя
        try:
            await callback.message.edit_text(
                text=callback.message.text + "\n\n✅ Запрос на повторную проверку отправлен. Ожидайте ответа.",
                reply_markup=None
            )
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение пользователя: {str(e)}")
            # Отправляем новое сообщение вместо редактирования
            await callback.message.answer("✅ Запрос на повторную проверку отправлен. Ожидайте ответа.")
        
        await callback.answer("✅ Запрос на проверку отправлен")
        
    except KeyError as e:
        logger.error(f"Заявка не найдена в storage: {str(e)}")
        await callback.answer("❌ Заявка была обновлена. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"Ошибка при запросе повторной проверки: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при отправке запроса")


@router.callback_query(F.data == "connection_restored")
async def connection_restored(callback: CallbackQuery):
    try:
        # Получаем ID заявки из текста сообщения или ищем по пользователю
        group_message_id = None
        
        # Пытаемся получить ID из reply_to_message
        if callback.message and callback.message.reply_to_message:
            group_message_id = callback.message.reply_to_message.message_id
        
        # Если не получилось, ищем по тексту сообщения
        if not group_message_id or group_message_id not in storage:
            # Ищем ID заявки в тексте сообщения
            message_text = callback.message.text or ""
            if "Заявка ID:" in message_text:
                try:
                    group_message_id = int(message_text.split("Заявка ID:")[1].strip().split(")")[0])
                except:
                    pass
        
        # Если всё ещё не нашли, ищем активную заявку модератора
        if not group_message_id or group_message_id not in storage:
            # Ищем последнюю активную заявку, где есть статусные сообщения
            for req_id, req_data in storage.items():
                if (isinstance(req_data, dict) and 
                    not req_data.get("is_completed", False) and 
                    "status_messages" in req_data and 
                    callback.message.message_id in req_data["status_messages"]):
                    group_message_id = req_id
                    break
        
        # ИСПРАВЛЕНИЕ: Проверяем существование заявки
        if not group_message_id or group_message_id not in storage:
            await callback.answer("❌ Заявка не найдена или была обновлена")
            return
        
        user_id = storage[group_message_id]["user_id"]
        
        # Используем клавиатуру ожидания вместо cancel_kb
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="✅ Связь восстановлена! Ожидайте.",
            reply_markup=kb.waiting_kb
        )
        
        # Обновляем статус заявки
        storage[group_message_id]["is_accepted"] = True
       
        if redis_client is not None:
            redis_client.update_request(str(group_message_id), {

        "is_accepted": True,
           
        })
        
        # ИСПРАВЛЕНИЕ: Безопасно удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем финальное статусное сообщение
        try:
            final_status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"✅ Связь восстановлена. Пользователь уведомлен.\nПроверил: {callback.from_user.full_name}",
                reply_to_message_id=group_message_id
            )
        except Exception as e:
            # Если не получилось с привязкой, отправляем без неё
            logger.warning(f"Не удалось отправить с привязкой к сообщению {group_message_id}: {str(e)}")
            final_status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"✅ Связь восстановлена. Пользователь уведомлен.\nПроверил: {callback.from_user.full_name}\n(Заявка ID: {group_message_id})"
            )

        # ИСПРАВЛЕНИЕ: Безопасно сохраняем ID финального статусного сообщения
        if group_message_id in storage:
            storage[group_message_id]["status_messages"] = [final_status_msg.message_id]
        
        # Удаляем текущее сообщение с кнопками
        await safe_delete_message(callback.bot, GROUP_ID, callback.message.message_id)
        
        await callback.answer("✅ Пользователь уведомлен")
        
    except KeyError as e:
        logger.error(f"Заявка не найдена в storage: {str(e)}")
        await callback.answer("❌ Заявка была обновлена")
    except Exception as e:
        logger.error(f"Ошибка при восстановлении связи: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data == "connection_still_bad")
async def connection_still_bad(callback: CallbackQuery):
    try:
        # Получаем ID заявки из текста сообщения или ищем по пользователю
        group_message_id = None
        
        # Пытаемся получить ID из reply_to_message
        if callback.message and callback.message.reply_to_message:
            group_message_id = callback.message.reply_to_message.message_id
        
        # Если не получилось, ищем по тексту сообщения
        if not group_message_id or group_message_id not in storage:
            # Ищем ID заявки в тексте сообщения
            message_text = callback.message.text or ""
            if "Заявка ID:" in message_text:
                try:
                    group_message_id = int(message_text.split("Заявка ID:")[1].strip().split(")")[0])
                except:
                    pass
        
        # Если всё ещё не нашли, ищем активную заявку модератора
        if not group_message_id or group_message_id not in storage:
            # Ищем последнюю активную заявку, где есть статусные сообщения
            for req_id, req_data in storage.items():
                if (isinstance(req_data, dict) and 
                    not req_data.get("is_completed", False) and 
                    "status_messages" in req_data and 
                    callback.message.message_id in req_data["status_messages"]):
                    group_message_id = req_id
                    break
        
        # ИСПРАВЛЕНИЕ: Проверяем существование заявки
        if not group_message_id or group_message_id not in storage:
            await callback.answer("❌ Заявка не найдена или была обновлена")
            return
        
        user_id = storage[group_message_id]["user_id"]
        
        # Создаем клавиатуру только с кнопкой проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])
        
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="😥 К сожалению, изменений не произошло. Попробуйте еще раз.",
            reply_markup=check_connection_kb
        )
        
        # ИСПРАВЛЕНИЕ: Безопасно удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        try:
            status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"❌ Связь не восстановлена. Пользователю отправлено уведомление.\nПроверил: {callback.from_user.full_name}",
                reply_to_message_id=group_message_id
            )
        except Exception as e:
            # Если не получилось с привязкой, отправляем без неё
            logger.warning(f"Не удалось отправить с привязкой к сообщению {group_message_id}: {str(e)}")
            status_msg = await send_message_with_retry(
                callback.bot,
                chat_id=GROUP_ID,
                text=f"❌ Связь не восстановлена. Пользователю отправлено уведомление.\nПроверил: {callback.from_user.full_name}\n(Заявка ID: {group_message_id})"
            )

        # ИСПРАВЛЕНИЕ: Безопасно сохраняем ID нового статусного сообщения
        if group_message_id in storage:
            storage[group_message_id]["status_messages"] = [status_msg.message_id]
        
        # Удаляем текущее сообщение с кнопками
        await safe_delete_message(callback.bot, GROUP_ID, callback.message.message_id)
        
        await callback.answer("✅ Пользователь уведомлен")
        
    except KeyError as e:
        logger.error(f"Заявка не найдена в storage: {str(e)}")
        await callback.answer("❌ Заявка была обновлена")
    except Exception as e:
        logger.error(f"Ошибка при обработке плохой связи: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")









@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    await callback.answer()




# ← ВСТАВЬ СЮДА НОВЫЙ ОБРАБОТЧИК
@router.callback_query(F.data == "copy_address")
async def copy_address(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_data = storage[group_message_id]
        adres = user_data.get("adres", "")
        
        if not adres:
            await callback.answer("❌ Адрес не найден")
            return

        # Отправляем ТОЛЬКО адрес в удобном для копирования формате
        copy_message = await callback.message.answer(
            f"📋 **Адрес для копирования:**\n\n`{adres}`\n\n"
            f"👆 *Нажмите на адрес для копирования*\n"
            f"🗑️ *Сообщение удалится через 10 секунд*",
            parse_mode="Markdown"
        )
        
        await callback.answer("📋 Адрес готов к копированию")
        
        # Удаляем сообщение через 10 секунд
        await asyncio.sleep(10)
        await safe_delete_message(callback.bot, GROUP_ID, copy_message.message_id)
        
    except Exception as e:
        logger.error(f"Ошибка при копировании адреса: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при получении адреса")



@router.callback_query(F.data == "bad_connection")
async def handle_bad_connection(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_id = storage[group_message_id]["user_id"]

        # Создаем клавиатуру для проверки связи
        check_connection_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ", callback_data="check_connection_again")]
        ])

        # Используем функцию с повторными попытками
        await send_message_with_retry(
            callback.bot,
            chat_id=user_id,
            text="⚠️ Связь с телевизором есть, НО не стабильна. Проверьте соединения, разъём RJ45, попробуйте сменить порт.",
            reply_markup=check_connection_kb
        )

        # Удаляем предыдущие статусные сообщения
        if "status_messages" in storage[group_message_id]:
            for msg_id in storage[group_message_id]["status_messages"]:
                await safe_delete_message(callback.bot, GROUP_ID, msg_id)

        # Отправляем новое статусное сообщение
        status_msg = await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"⚠️ Уведомление о плохой связи отправлено пользователю.\nОтправил: {callback.from_user.full_name}",
            reply_to_message_id=group_message_id
        )

        # Сохраняем ID нового статусного сообщения
        storage[group_message_id]["status_messages"] = [status_msg.message_id]

        await callback.answer("✅ Пользователь уведомлен о плохой связи")

    except Exception as e:
        logger.error(f"Ошибка при обработке плохой связи: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data == "contact_user")
async def contact_user(callback: CallbackQuery):
    try:
        # Проверяем наличие reply_to_message
        if not callback.message or not callback.message.reply_to_message:
            await callback.answer("❌ Не удалось определить заявку")
            return
            
        group_message_id = callback.message.reply_to_message.message_id
        
        # Проверяем наличие заявки в хранилище
        if group_message_id not in storage:
            logger.warning(f"Заявка с ID {group_message_id} не найдена в хранилище")
            await callback.answer("❌ Заявка не найдена в системе")
            return

        user_data = storage[group_message_id]
        user_id = user_data.get("user_id")
        user_name = user_data.get("user_name", "Неизвестный")
        
        if not user_id:
            await callback.answer("❌ Не удалось найти данные пользователя")
            return

        # Создаем ссылку на личный чат с пользователем
        user_link = f"tg://user?id={user_id}"
        
        # Отправляем ОДНО компактное сообщение в основную группу
        await send_message_with_retry(
            callback.bot,
            chat_id=GROUP_ID,
            text=f"💬 [{user_name}]({user_link}) ← {callback.from_user.first_name}",
            parse_mode="Markdown",
            reply_to_message_id=group_message_id,
            disable_web_page_preview=True
        )
        
        await callback.answer("✅ Ссылка создана")
        
    except Exception as e:
        logger.error(f"Ошибка при создании связи с монтажником: {str(e)}", exc_info=True)
        await callback.answer("❌ Ошибка при создании ссылки")



# ========== CALLBACK ОБРАБОТЧИКИ ДЛЯ REDIS ==========

@router.callback_query(F.data == "confirm_redis_clear")
async def confirm_redis_clear(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Только для администраторов")
        return
    
    try:
        if redis_client is not None:
            # Очищаем Redis (если есть метод clear_all_requests)
            try:
                redis_client.clear_all_requests()
                await callback.message.edit_text("✅ Redis очищен успешно!")
            except AttributeError:
                # Если метода нет, используем альтернативный способ
                await callback.message.edit_text("⚠️ Метод очистки Redis недоступен. Используйте /sync_force")
        else:
            await callback.message.edit_text("❌ Redis недоступен")
            
        await callback.answer("✅ Redis очищен")
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка очистки Redis: {str(e)}")
        await callback.answer("❌ Ошибка")


@router.callback_query(F.data == "cancel_redis_clear")
async def cancel_redis_clear(callback: CallbackQuery):
    await callback.message.edit_text("❌ Очистка Redis отменена")
    await callback.answer("✅ Отменено")




@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    try:
        current_state = await state.get_state()

        if not current_state:
            await message.answer("❌ Нет активной операции для отмены.")
            return

        # Проверяем все возможные финальные состояния
        final_states = [Reg.final_photo.state, OpsReplacement.final_photo.state, TvReplacement.final_photo.state]
        
        if current_state in final_states:
            data = await state.get_data()
            group_message_id = data.get("group_message_id")

            if group_message_id and group_message_id in storage and storage.get(group_message_id, {}).get("is_accepted", False):
                await message.answer("❌ На финальном этапе отмена невозможна!")
                return

        await state.clear()
        await message.answer("❎ Операция отменена", reply_markup=kb.main)
        logger.info(f"Операция отменена пользователем {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при отмене: {str(e)}", exc_info=True)
        await message.answer("❌ Ошибка при отмене. Попробуйте еще раз.")



@router.message(Command("sync_check"))
async def check_sync(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        redis_count = 0
        db_count = 0
        
        # Считаем Redis
        if redis_client is not None:
            try:
                redis_data = redis_client.get_all_active_requests()
                redis_count = len(redis_data)
            except:
                redis_count = "Недоступен"
        
        # Считаем БД
        try:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM requests WHERE status != "completed"')
                db_count = cursor.fetchone()[0]
        except Exception as e:
            db_count = f"Ошибка: {str(e)}"
        
        await message.answer(
            f"🔄 **Проверка синхронизации:**\n\n"
            f"📡 Redis: {redis_count} заявок\n"
            f"💾 БД: {db_count} заявок\n"
            f"🧠 Storage: {len(storage)} заявок\n\n"
            f"ℹ️ Используйте /sync_force для принудительной синхронизации"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка проверки: {str(e)}")


@router.message(Command("broadcast"))
async def broadcast_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    # Получаем текст после команды
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("📝 Использование: /broadcast <текст сообщения>")
        return
    
    # Получаем всех активных пользователей
    active_users = set()
    for req_data in storage.values():
        if isinstance(req_data, dict) and req_data.get("user_id"):
            active_users.add(req_data["user_id"])
    
    sent_count = 0
    for user_id in active_users:
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"📢 **Уведомление от администрации:**\n\n{text}"
            )
            sent_count += 1
            await asyncio.sleep(0.1)  # Избегаем лимитов
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {str(e)}")
    
    await message.answer(f"✅ Сообщение отправлено {sent_count} пользователям")


@router.message(Command("monitor"))
async def system_monitor(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        import psutil
        import os
        
        # Системная информация
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Информация о боте
        process = psutil.Process(os.getpid())
        bot_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        monitor_text = f"🖥️ **Мониторинг системы:**\n\n"
        monitor_text += f"💾 ОЗУ: {memory.percent}% ({memory.used // 1024 // 1024} MB / {memory.total // 1024 // 1024} MB)\n"
        monitor_text += f"💽 Диск: {disk.percent}% ({disk.used // 1024 // 1024 // 1024} GB / {disk.total // 1024 // 1024 // 1024} GB)\n"
        monitor_text += f"⚡ CPU: {cpu_percent}%\n\n"
        monitor_text += f"🤖 **Бот:**\n"
        monitor_text += f"📊 Память бота: {bot_memory:.1f} MB\n"
        monitor_text += f"📝 Активных заявок: {len(storage)}\n"
        monitor_text += f"🗄️ Размер БД: {os.path.getsize(db.db_path) // 1024} KB"
        
        await message.answer(monitor_text)
        
    except ImportError:
        await message.answer("❌ Для мониторинга установите: pip install psutil")
    except Exception as e:
        await message.answer(f"❌ Ошибка мониторинга: {str(e)}")

@router.message(Command("clear_redis"))
async def clear_redis(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        if redis_client is not None:
            # Удаляем все ключи заявок
            keys = redis_client.redis.keys("request:*")
            if keys:
                redis_client.redis.delete(*keys)
            
            # Очищаем список активных заявок
            redis_client.redis.delete("active_requests")
            
            await message.answer(f"✅ Redis очищен. Удалено ключей: {len(keys)}")
        else:
            await message.answer("❌ Redis недоступен")
    except Exception as e:
        logger.error(f"Ошибка очистки Redis: {str(e)}")
        await message.answer("❌ Ошибка очистки Redis")


@router.message()
async def other_messages(message: Message, state: FSMContext):
    if message.chat.type != 'private':
       return

    current_state = await state.get_state()

    if current_state:
        # Проверяем, ожидается ли фото
        photo_states = [
            Reg.photo.state, Reg.photo2.state, Reg.photo3.state, Reg.final_photo.state,
            OpsReplacement.ops_photo.state, OpsReplacement.screen_photo.state, OpsReplacement.final_photo.state,
            TvReplacement.tv_photo.state, TvReplacement.final_photo.state
        ]
        
        if current_state in photo_states:
            await message.answer("📸 Пожалуйста, отправьте фото.")
        else:
            await message.answer("📝 Пожалуйста, введите текст или используйте кнопки.")
        return

    await message.reply("⚠️ Используй кнопки меню", reply_markup=kb.main)








# Добавь новый обработчик для игнорирования сообщений в группах
@router.message()
async def ignore_messages_in_groups(message: Message):
    if message.chat.type != 'private':
        return

    # Игнорируем все сообщения в группах, которые не обработались другими обработчиками
    pass