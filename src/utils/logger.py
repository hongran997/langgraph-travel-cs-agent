"""
日志工具
基于 structlog 提供结构化 JSON 日志输出
"""
import structlog
from src.config.settings import settings


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    structlog.configure(
        processors=[
            structlog.processors.JSONRenderer(),
        ]
    )
    return structlog.get_logger(name).bind(
        app_name=settings.app_name,
        env=settings.app_env,
    )