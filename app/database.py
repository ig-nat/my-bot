import sqlite3
import datetime
import logging
from typing import Dict
import os
import platform

logger = logging.getLogger(__name__)

def get_db_path():
    """Определяем путь к базе данных в зависимости от операционной системы"""
    if platform.system() == "Windows":
        return "bot_data.db"
    else:
        nas_path = "/volume2/RussOutdoor/bot_data.db"
        if os.path.exists("/volume2/RussOutdoor/"):
            return nas_path
        else:
            return "bot_data.db"

DB_PATH = get_db_path()

# Путь к папке для хранения фотографий
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(BASE_DIR, 'photos')

# Проверяем и создаём папку photos, если её нет
if not os.path.exists(PHOTO_DIR):
    try:
        os.makedirs(PHOTO_DIR, exist_ok=True)
        logger.info(f"Папка для фото создана: {PHOTO_DIR}")
    except Exception as e:
        logger.error(f"Ошибка создания папки для фото: {str(e)}")

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создаем таблицу для заявок с новым полем photo_path
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS requests (
                        id INTEGER PRIMARY KEY,
                        request_id TEXT UNIQUE,
                        user_id INTEGER,
                        user_name TEXT,
                        address TEXT,
                        request_type TEXT DEFAULT 'regular',
                        gid TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        is_accepted BOOLEAN DEFAULT FALSE,
                        moderator_name TEXT,
                        photo_path TEXT
                    )
                ''')
                
                # Создаем индексы для быстрого поиска
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON requests(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON requests(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON requests(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_type ON requests(request_type)')
                
                conn.commit()
                logger.info(f"База данных инициализирована: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {str(e)}")
    
    def save_request(self, request_id: str, user_id: int, user_name: str, 
                    address: str = "", request_type: str = "regular", gid: str = "", photo_path: str = ""):
        """Сохранение заявки в базу данных с путем к фото"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO requests 
                    (request_id, user_id, user_name, address, request_type, gid, created_at, photo_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (request_id, user_id, user_name, address, request_type, gid, datetime.datetime.now(), photo_path))
                conn.commit()
                logger.info(f"Заявка {request_id} сохранена в БД с фото: {photo_path}")
                
        except Exception as e:
            logger.error(f"Ошибка сохранения заявки в БД: {str(e)}")
    
    def update_request_status(self, request_id: str, status: str, moderator_name: str = ""):
        """Обновление статуса заявки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                completed_at = datetime.datetime.now() if status == 'completed' else None
                cursor.execute('''
                    UPDATE requests 
                    SET status = ?, completed_at = ?, moderator_name = ?
                    WHERE request_id = ?
                ''', (status, completed_at, moderator_name, request_id))
                conn.commit()
                logger.info(f"Статус заявки {request_id} обновлен на {status}")
                
        except Exception as e:
            logger.error(f"Ошибка обновления статуса заявки: {str(e)}")
    
    def update_request_gid(self, request_id: str, gid: str):
        """Обновление GiD заявки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE requests SET gid = ?, is_accepted = TRUE WHERE request_id = ?
                ''', (gid, request_id))
                conn.commit()
                logger.info(f"GiD заявки {request_id} обновлен: {gid}")
                
        except Exception as e:
            logger.error(f"Ошибка обновления GiD: {str(e)}")
    
    def get_statistics_today(self) -> Dict:
        """Статистика за сегодня"""
        try:
            today = datetime.date.today()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика за сегодня
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests 
                    WHERE DATE(created_at) = ?
                ''', (today,))
                
                stats = cursor.fetchone()
                
                # Статистика по пользователям за сегодня
                cursor.execute('''
                    SELECT 
                        user_name,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests 
                    WHERE DATE(created_at) = ?
                    GROUP BY user_name
                    ORDER BY total DESC
                ''', (today,))
                
                user_stats = cursor.fetchall()
                
                return {
                    'total': stats[0] or 0,
                    'completed': stats[1] or 0,
                    'pending': (stats[0] or 0) - (stats[1] or 0),
                    'regular': stats[2] or 0,
                    'ops': stats[3] or 0,
                    'tv': stats[4] or 0,
                    'users': user_stats
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики за сегодня: {str(e)}")
            return {}
    
    def get_statistics_all_time(self) -> Dict:
        """Статистика за все время"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика за все время
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests
                ''')
                
                stats = cursor.fetchone()
                
                # Статистика по пользователям за все время
                cursor.execute('''
                    SELECT 
                        user_name,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests 
                    GROUP BY user_name
                    ORDER BY total DESC
                ''')
                
                user_stats = cursor.fetchall()
                
                return {
                    'total': stats[0] or 0,
                    'completed': stats[1] or 0,
                    'pending': (stats[0] or 0) - (stats[1] or 0),
                    'regular': stats[2] or 0,
                    'ops': stats[3] or 0,
                    'tv': stats[4] or 0,
                    'users': user_stats
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики за все время: {str(e)}")
            return {}
    
    def get_statistics_period(self, start_date: datetime.date, end_date: datetime.date) -> Dict:
        """Статистика за период"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика за период
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests 
                    WHERE DATE(created_at) BETWEEN ? AND ?
                ''', (start_date, end_date))
                
                stats = cursor.fetchone()
                
                # Статистика по пользователям за период
                cursor.execute('''
                    SELECT 
                        user_name,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN request_type = 'regular' THEN 1 ELSE 0 END) as regular,
                        SUM(CASE WHEN request_type = 'OPS' THEN 1 ELSE 0 END) as ops,
                        SUM(CASE WHEN request_type = 'TV' THEN 1 ELSE 0 END) as tv
                    FROM requests 
                    WHERE DATE(created_at) BETWEEN ? AND ?
                    GROUP BY user_name
                    ORDER BY total DESC
                ''', (start_date, end_date))
                
                user_stats = cursor.fetchall()
                
                return {
                    'total': stats[0] or 0,
                    'completed': stats[1] or 0,
                    'pending': (stats[0] or 0) - (stats[1] or 0),
                    'regular': stats[2] or 0,
                    'ops': stats[3] or 0,
                    'tv': stats[4] or 0,
                    'users': user_stats,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики за период: {str(e)}")
            return {}

# Создаем глобальный экземпляр базы данных
db = Database()
