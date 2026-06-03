"""Application configuration — all fields use default_factory for env var reads.
Neon-compatible: supports DATABASE_URL (connection pooling via pgBouncer) as
the primary connection string, falling back to host/port/user/password parts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

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

    @property
    def primary_model(self) -> str:
        return self.model


@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    enabled: bool = field(
        default_factory=lambda: os.getenv("REDIS_ENABLED", "true").lower() == "true"
    )
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class DatabricksConfig:
    host: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    token: str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    http_path: str = field(default_factory=lambda: os.getenv("DATABRICKS_HTTP_PATH", ""))
    catalog: str = field(default_factory=lambda: os.getenv("DATABRICKS_CATALOG", "main"))


def _parse_neon_url(raw: str):
    """Parse a Neon DATABASE_URL and return (host, port, user, password, dbname)."""
    p = urlparse(raw)
    return (
        p.hostname or "localhost",
        p.port or 5432,
        p.username or "postgres",
        p.password or "",
        (p.path or "/governance_db").lstrip("/"),
    )


@dataclass
class VectorDBConfig:
    # If DATABASE_URL is set (Neon style) it overrides individual parts.
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "governance_db"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    sslmode: str = field(default_factory=lambda: os.getenv("POSTGRES_SSLMODE", "require"))

    table_name: str = field(
        default_factory=lambda: os.getenv("VECTOR_TABLE", "document_embeddings")
    )
    embedding_dim: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "1536"))
    )
    collection_name: str = field(
        default_factory=lambda: os.getenv("VECTOR_COLLECTION", "governance_docs")
    )

    def __post_init__(self):
        """If DATABASE_URL is set, override individual fields from it."""
        if self.database_url:
            h, port, u, pw, db = _parse_neon_url(self.database_url)
            self.host = h
            self.port = port
            self.user = u
            self.password = pw
            self.database = db

    @property
    def connection_string(self) -> str:
        """psycopg2-compatible connection string with SSL for Neon."""
        if self.database_url:
            # Neon provides a URL already; ensure psycopg2 driver and sslmode
            url = self.database_url
            # Replace asyncpg/postgres scheme with psycopg2-compatible one
            url = url.replace("postgresql://", "postgresql+psycopg2://")
            url = url.replace("postgres://", "postgresql+psycopg2://")
            if "sslmode" not in url:
                url += "?sslmode=require"
            return url
        ssl = f"?sslmode={self.sslmode}" if self.sslmode else ""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}{ssl}"
        )

    @property
    def psycopg2_dsn(self) -> str:
        """Raw psycopg2 connect kwargs as DSN string (no SQLAlchemy prefix)."""
        if self.database_url:
            url = self.database_url
            url = url.replace("postgresql+psycopg2://", "postgresql://")
            url = url.replace("postgres://", "postgresql://")
            return url
        ssl = f" sslmode={self.sslmode}" if self.sslmode else ""
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}{ssl}"
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


DATA_PRODUCTS = ["retention", "bookings", "cac", "ltv"]

_config_singleton: AppConfig | None = None


def get_config() -> AppConfig:
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = AppConfig()
    return _config_singleton


config = get_config()


def reset_config() -> None:
    global _config_singleton, config
    _config_singleton = None
    config = get_config()
