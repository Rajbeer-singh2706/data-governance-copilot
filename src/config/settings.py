"""Application configuration — all fields use default_factory for env var reads."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))
    api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    temperature: float = 0.1
    max_tokens: int = 2048
    fallback_models: list = field(
        default_factory=lambda: [
            "gpt-4o-mini",
            "anthropic/claude-haiku-4-5",
            "gemini/gemini-1.5-flash",
        ]
    )


@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    enabled: bool = field(
        default_factory=lambda: os.getenv("REDIS_ENABLED", "true").lower() == "true"
    )


@dataclass
class DatabricksConfig:
    host: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    token: str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    http_path: str = field(default_factory=lambda: os.getenv("DATABRICKS_HTTP_PATH", ""))


@dataclass
class VectorDBConfig:
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "governance_db"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass
class AppConfig:
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    sqlite_path: str = field(default_factory=lambda: os.getenv("SQLITE_PATH", "./data/memory.db"))
    llm: LLMConfig = field(default_factory=LLMConfig)
    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)


_config_singleton: AppConfig | None = None


def get_config() -> AppConfig:
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = AppConfig()
    return _config_singleton


def reset_config() -> None:
    """Reset singleton — for testing only."""
    global _config_singleton
    _config_singleton = None
