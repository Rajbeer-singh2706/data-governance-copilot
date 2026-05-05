import os 
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class LLMConfig:
    provider:    str = os.getenv("LLM_PROVIDER", "openai")
    model:       str = os.getenv("LLM_MODEL",    "gpt-4o")
    api_key:     str = os.getenv("OPENAI_API_KEY","")
    temperature: float = 0.1
    max_tokens:  int   = 4096

@dataclass
class DatabricksConfig:
    host:      str = os.getenv("DATABRICKS_HOST",  "")
    token:     str = os.getenv("DATABRICKS_TOKEN", "")
    http_path: str = os.getenv("DATABRICKS_HTTP_PATH", "")
    catalog:   str = os.getenv("DATABRICKS_CATALOG","main")
    schema:    str = os.getenv("DATABRICKS_SCHEMA","analytics")

@dataclass
class AppConfig:
    debug:       bool = os.getenv("DEBUG","false").lower()=="true"
    log_level:   str  = os.getenv("LOG_LEVEL","INFO")
    enable_mock: bool = os.getenv("ENABLE_MOCK","true").lower()=="true"

    llm:         LLMConfig        = field(default_factory=LLMConfig)
    databricks:  DatabricksConfig = field(default_factory=DatabricksConfig)

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