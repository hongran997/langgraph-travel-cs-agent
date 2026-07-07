"""
Redis 服务
提供短期缓存、会话存储、工单状态存储等功能
"""
import json
from datetime import datetime, timedelta
import redis
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedisService:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        self._test_connection()
    
    def _test_connection(self):
        try:
            self.client.ping()
            logger.info("redis_connection_successful", host=settings.redis_host, port=settings.redis_port)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise
    
    def set(self, key: str, value: dict, expire_seconds: int = 3600) -> bool:
        try:
            serialized = json.dumps(value)
            result = self.client.set(key, serialized, ex=expire_seconds)
            logger.debug("redis_set_success", key=key, expire_seconds=expire_seconds)
            return result
        except Exception as e:
            logger.error("redis_set_failed", key=key, error=str(e))
            return False
    
    def get(self, key: str) -> dict | None:
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("redis_get_failed", key=key, error=str(e))
            return None
    
    def delete(self, key: str) -> int:
        try:
            result = self.client.delete(key)
            logger.debug("redis_delete_success", key=key)
            return result
        except Exception as e:
            logger.error("redis_delete_failed", key=key, error=str(e))
            return 0
    
    def set_session(self, session_id: str, data: dict) -> bool:
        key = f"session:{session_id}"
        return self.set(key, data, expire_seconds=86400)
    
    def get_session(self, session_id: str) -> dict | None:
        key = f"session:{session_id}"
        return self.get(key)
    
    def delete_session(self, session_id: str) -> int:
        key = f"session:{session_id}"
        return self.delete(key)
    
    def set_ticket(self, ticket_id: str, data: dict) -> bool:
        key = f"ticket:{ticket_id}"
        return self.set(key, data, expire_seconds=604800)
    
    def get_ticket(self, ticket_id: str) -> dict | None:
        key = f"ticket:{ticket_id}"
        return self.get(key)
    
    def increment_counter(self, key: str) -> int:
        try:
            result = self.client.incr(key)
            logger.debug("redis_increment_success", key=key)
            return result
        except Exception as e:
            logger.error("redis_increment_failed", key=key, error=str(e))
            return 0