"""
Central configuration for Data Governance Copilot.
All environment variables and system settings are managed here.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "openai")  # openai | azure_openai
    model: str = os.getenv("LLM_MODEL", "gpt-4o")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    azure_endpoint: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    temperature: float = 0.1
    max_tokens: int = 4096


@dataclass
class DatabricksConfig:
    host: str = os.getenv("DATABRICKS_HOST", "")
    token: str = os.getenv("DATABRICKS_TOKEN", "")
    http_path: str = os.getenv("DATABRICKS_HTTP_PATH", "")
    catalog: str = os.getenv("DATABRICKS_CATALOG", "main")
    schema: str = os.getenv("DATABRICKS_SCHEMA", "analytics")


@dataclass
class CollibraConfig:
    base_url: str = os.getenv("COLLIBRA_BASE_URL", "")
    username: str = os.getenv("COLLIBRA_USERNAME", "")
    password: str = os.getenv("COLLIBRA_PASSWORD", "")
    community_id: str = os.getenv("COLLIBRA_COMMUNITY_ID", "")


@dataclass
class JiraConfig:
    base_url: str = os.getenv("JIRA_BASE_URL", "")
    email: str = os.getenv("JIRA_EMAIL", "")
    api_token: str = os.getenv("JIRA_API_TOKEN", "")
    project_key: str = os.getenv("JIRA_PROJECT_KEY", "DATA")
    default_assignee: Optional[str] = os.getenv("JIRA_DEFAULT_ASSIGNEE")


@dataclass
class SharePointConfig:
    tenant_id: str = os.getenv("SHAREPOINT_TENANT_ID", "")
    client_id: str = os.getenv("SHAREPOINT_CLIENT_ID", "")
    client_secret: str = os.getenv("SHAREPOINT_CLIENT_SECRET", "")
    site_url: str = os.getenv("SHAREPOINT_SITE_URL", "")


@dataclass
class VectorStoreConfig:
    provider: str = os.getenv("VECTOR_STORE", "faiss")  # faiss | chroma
    persist_directory: str = os.getenv("VECTOR_STORE_PATH", "./data/vectorstore")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class AppConfig:
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "./logs/copilot.log")
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    timeout_seconds: int = int(os.getenv("TIMEOUT_SECONDS", "60"))
    enable_mock: bool = os.getenv("ENABLE_MOCK", "true").lower() == "true"

    # Sub-configs
    llm: LLMConfig = field(default_factory=LLMConfig)
    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)
    collibra: CollibraConfig = field(default_factory=CollibraConfig)
    jira: JiraConfig = field(default_factory=JiraConfig)
    sharepoint: SharePointConfig = field(default_factory=SharePointConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)


# Singleton config instance
config = AppConfig()


# Data product definitions
DATA_PRODUCTS = {
    "bookings": {
        "description": "Total revenue committed via signed contracts",
        "owner": "Revenue Operations",
        "table": "analytics.bookings_fact",
        "key_metrics": ["total_bookings", "net_new_bookings", "expansion_bookings"],
    },
    "retention": {
        "description": "Percentage of customers renewing subscriptions",
        "owner": "Customer Success",
        "table": "analytics.retention_metrics",
        "key_metrics": ["gross_retention_rate", "net_retention_rate", "churn_rate"],
    },
    "ltv": {
        "description": "Predicted total revenue from a customer over their lifetime",
        "owner": "Data Science",
        "table": "analytics.customer_ltv",
        "key_metrics": ["avg_ltv", "ltv_by_segment", "ltv_cac_ratio"],
    },
    "cac": {
        "description": "Cost to acquire a new customer",
        "owner": "Marketing Analytics",
        "table": "analytics.cac_metrics",
        "key_metrics": ["blended_cac", "paid_cac", "organic_cac", "payback_period"],
    },
}
