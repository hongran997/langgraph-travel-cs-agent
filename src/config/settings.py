"""
配置模块
从 .env 文件加载环境变量，提供全局配置访问
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "langgraph-travel-cs-agent"
    app_env: str = "development"
    app_port: int = 8000

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""
    milvus_collection_name: str = "travel_knowledge"

    external_rag_url: str = "http://localhost:8081/api/v1/rag/query"
    internal_rag_url: str = "http://localhost:8082/api/v1/rag/query"

    openai_api_key: str = ""
    openai_api_base: str = "http://localhost:8080/v1"

    log_level: str = "INFO"
    checkpoint_enabled: bool = True
    max_conversation_history: int = 50

    node_retry_enabled: bool = True
    node_retry_max_attempts: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()