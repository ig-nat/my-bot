import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    # ... существующие методы ...
    
    def save_request(self, request_id: str, request_data: dict):
        """Сохранение заявки в Redis"""
        try:
            # Сериализуем данные заявки
            serialized_data = json.dumps(request_data, default=str, ensure_ascii=False)
            
            # Сохраняем с префиксом для удобства
            key = f"request:{request_id}"
            self.redis.set(key, serialized_data)
            
            # Добавляем в список активных заявок
            self.redis.sadd("active_requests", request_id)
            
            logger.debug(f"Заявка {request_id} сохранена в Redis")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения заявки в Redis: {str(e)}")
    
    def get_request(self, request_id: str) -> Optional[dict]:
        """Получение заявки из Redis"""
        try:
            key = f"request:{request_id}"
            data = self.redis.get(key)
            
            if data:
                return json.loads(data.decode('utf-8'))
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения заявки из Redis: {str(e)}")
            return None
    
    def get_all_active_requests(self) -> Dict[int, dict]:
        """Получение всех активных заявок"""
        try:
            active_request_ids = self.redis.smembers("active_requests")
            requests = {}
            
            for request_id_bytes in active_request_ids:
                request_id = request_id_bytes.decode('utf-8')
                request_data = self.get_request(request_id)
                
                if request_data and not request_data.get("is_completed", False):
                    try:
                        requests[int(request_id)] = request_data
                    except ValueError:
                        # Если request_id не число, пропускаем
                        continue
                else:
                    # Удаляем завершенную заявку из активных
                    self.redis.srem("active_requests", request_id)
            
            logger.info(f"Загружено {len(requests)} активных заявок из Redis")
            return requests
            
        except Exception as e:
            logger.error(f"Ошибка загрузки заявок из Redis: {str(e)}")
            return {}
    
    def complete_request(self, request_id: str):
        """Помечаем заявку как завершенную"""
        try:
            # Получаем данные заявки
            request_data = self.get_request(request_id)
            if request_data:
                # Помечаем как завершенную
                request_data["is_completed"] = True
                request_data["completed_at"] = str(datetime.datetime.now())
                
                # Сохраняем обновленные данные
                self.save_request(request_id, request_data)
                
                # Удаляем из активных заявок
                self.redis.srem("active_requests", request_id)
                
                logger.info(f"Заявка {request_id} помечена как завершенная")
            
        except Exception as e:
            logger.error(f"Ошибка завершения заявки в Redis: {str(e)}")
    
    def update_request(self, request_id: str, updates: dict):
        """Обновление данных заявки"""
        try:
            request_data = self.get_request(request_id)
            if request_data:
                request_data.update(updates)
                self.save_request(request_id, request_data)
                logger.debug(f"Заявка {request_id} обновлена")
            
        except Exception as e:
            logger.error(f"Ошибка обновления заявки в Redis: {str(e)}")
