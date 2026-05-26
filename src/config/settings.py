"""
src/config/settings.py
Application configuration — loaded once at import time.

All values come from environment variables (or .env file via python-dotenv).
Defaults are chosen to work out-of-the-box in local dev with ENABLE_MOCK=true.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider configuration. Supports 'groq' and 'openai'."""

    provider:      str   = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq"))
    primary_model: str   = field(default_factory=lambda: os.getenv(
        "LLM_MODEL", "llama-3.3-70b-versatile"   # plain model name, no prefix
    ))
    # API key — resolves from the right env var based on provider
    api_key:       str   = field(default_factory=lambda: (
        os.getenv("GROQ_API_KEY", "")
        if os.getenv("LLM_PROVIDER", "groq").lower() == "groq"
        else os.getenv("OPENAI_API_KEY", "")
    ))

    temperature:   float = 0.0
    max_tokens:    int   = 4096
    timeout:       int   = 30
    max_retries:   int   = 3

    fallback_models: list = field(default_factory=lambda: [
        "gpt-4o-mini",
        "anthropic/claude-haiku-4-5",
        "gemini/gemini-1.5-flash",
    ])

    @property
    def model(self) -> str:
        """Backward-compat alias for primary_model."""
        return self.primary_model

@dataclass
class DatabricksConfig:
    host:      str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    token:     str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    http_path: str = field(default_factory=lambda: os.getenv("DATABRICKS_HTTP_PATH", ""))
    catalog:   str = field(default_factory=lambda: os.getenv("DATABRICKS_CATALOG", "main"))
    schema:    str = field(default_factory=lambda: os.getenv("DATABRICKS_SCHEMA", "analytics"))


@dataclass
class RedisConfig:
    host:        str  = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port:        int  = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    password:    str  = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    db:          int  = 0
    ttl_seconds: int  = 3600
    # Set REDIS_ENABLED=false in .env if you don't have Redis running locally
    enabled:     bool = field(default_factory=lambda: (
        os.getenv("REDIS_ENABLED", "true").lower() == "true"
    ))

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class AppConfig:
    debug:       bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level:   str  = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    enable_mock: bool = field(default_factory=lambda: os.getenv("ENABLE_MOCK", "true").lower() == "true")

    llm:         LLMConfig        = field(default_factory=LLMConfig)
    databricks:  DatabricksConfig = field(default_factory=DatabricksConfig)
    redis:       RedisConfig      = field(default_factory=RedisConfig)


# Singleton — created once at import time, used everywhere
config = AppConfig()

# ── Data product registry ──────────────────────────────────────────────────

DATA_PRODUCTS = {
    "retention": {
        "description": "% of customers renewing subscriptions",
        "owner":       "Customer Success",
        "table":       "analytics.retention_metrics",
        "key_metrics": ["gross_retention_rate", "churn_rate"],
    },
    "bookings": {
        "description": "Total revenue from signed contracts",
        "owner":       "Revenue Operations",
        "table":       "analytics.bookings_fact",
        "key_metrics": ["total_bookings", "net_new_bookings"],
    },
    "cac": {
        "description": "Cost to acquire a new customer",
        "owner":       "Marketing Analytics",
        "table":       "analytics.cac_metrics",
        "key_metrics": ["blended_cac", "payback_period_months"],
    },
    "ltv": {
        "description": "Predicted total revenue per customer",
        "owner":       "Data Science",
        "table":       "analytics.customer_ltv",
        "key_metrics": ["avg_ltv", "ltv_cac_ratio"],
    },
}
