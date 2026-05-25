import os 
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
#load_dotenv(r'D:\secrets\global.env')

@dataclass
class LLMConfig:
    provider:      str   = os.getenv("LLM_PROVIDER", "openai")
    primary_model: str   = os.getenv("LLM_MODEL",    "gpt-4o")  # renamed from model
    api_key:       str   = os.getenv("OPENAI_API_KEY", "")
    temperature:   float = 0.0           # was 0.1 — changed for determinism
    max_tokens:    int   = 4096
    timeout:       int   = 30            # NEW: per-call timeout seconds
    max_retries:   int   = 3             # NEW: retries before next fallback

    fallback_models: list = field(default_factory=lambda: [
        "gpt-4o-mini",
        "anthropic/claude-haiku-4-5",
        "gemini/gemini-1.5-flash",
    ])

    @property
    def model(self) -> str:              # backward-compat alias
        return self.primary_model

@dataclass
class DatabricksConfig:
    host:      str = os.getenv("DATABRICKS_HOST",  "")
    token:     str = os.getenv("DATABRICKS_TOKEN", "")
    http_path: str = os.getenv("DATABRICKS_HTTP_PATH", "")
    catalog:   str = os.getenv("DATABRICKS_CATALOG","main")
    schema:    str = os.getenv("DATABRICKS_SCHEMA","analytics")

@dataclass
class RedisConfig:
    host:        str  = os.getenv("REDIS_HOST",     "localhost")
    port:        int  = int(os.getenv("REDIS_PORT", "6379"))
    password:    str  = os.getenv("REDIS_PASSWORD", "")
    db:          int  = 0
    ttl_seconds: int  = 3600
    enabled:     bool = os.getenv("REDIS_ENABLED", "true").lower() == "true" 

    @property
    def url(self) -> str:
        print(f"URL: {self.host}, {self.password}, {self.db}")
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
@dataclass
class AppConfig:
    debug:       bool = os.getenv("DEBUG","false").lower()=="true"
    log_level:   str  = os.getenv("LOG_LEVEL","INFO")
    enable_mock: bool = os.getenv("ENABLE_MOCK","true").lower()=="true"

    llm:         LLMConfig        = field(default_factory=LLMConfig)
    databricks:  DatabricksConfig = field(default_factory=DatabricksConfig)
    redis:       RedisConfig      = field(default_factory=RedisConfig)  # NEW

# Singleton — created once, imported everywhere
config = AppConfig()


# Data product registry
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