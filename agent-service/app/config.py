from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# config.py 位于 agent-service/app，下一级父目录就是 agent-service。
# 使用绝对路径后，无论从项目根目录、agent-service 目录还是 IDE 启动，
# 都会读取同一份 agent-service/.env。
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="TRAINMIND_",
        extra="ignore",
    )

    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8010
    business_base_url: str = "http://127.0.0.1:8000"
    request_timeout_seconds: float = 8.0
    mcp_enabled: bool = False
    mcp_server_url: str = "http://127.0.0.1:8011/sse"
    llm_enabled: bool = False
    llm_model: str = "deepseek-chat"
    llm_base_url: str | None = "https://api.deepseek.com"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 60.0
    max_results: int = 5
    session_ttl_minutes: int = 60
    session_store: str = "hybrid"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "trainmind:agent:conversation"
    mysql_url: str = (
        "mysql+asyncmy://root@127.0.0.1:3306/business?charset=utf8mb4"
    )
    knowledge_dir: str = "../knowledge"
    rag_top_k: int = 4
    rag_pgvector_enabled: bool = False
    rag_postgres_dsn: str = "postgresql://trainmind:trainmind@127.0.0.1:5432/trainmind"
    rag_embedding_model: str = "text-embedding-v4"
    rag_embedding_dimension: int = 1024
    rag_embedding_base_url: str | None = None
    rag_embedding_api_key: str | None = None

    @property
    def env_file_dir(self) -> Path:
        return ENV_FILE.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
