"""
src/agents/information_agent.py

Fetches structured metrics from Databricks SQL.
Requires DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH env vars.
Raises clearly if credentials are missing — caught by BaseAgent.execute().
"""
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.logging_utils import with_retry
from config.settings import DATA_PRODUCTS


class DatabricksConnector:
    """Thin wrapper around databricks-sql-connector."""

    def __init__(self, config):
        self.config = config
        self._connection = None

    def connect(self):
        from databricks import sql as dbsql
        self._connection = dbsql.connect(
            server_hostname=self.config.host,
            http_path=self.config.http_path,
            access_token=self.config.token,
        )

    @with_retry(max_retries=3)
    def query(self, sql_query: str) -> List[Dict]:
        if not self._connection:
            self.connect()
        with self._connection.cursor() as cursor:
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        if self._connection:
            self._connection.close()


class InformationAgent(BaseAgent):
    """
    Fetches structured metrics from Databricks SQL Warehouse.
    Raises ConfigurationError when credentials are absent.
    """
    name = "information_agent"
    description = "Queries structured data for metrics and facts"
    capabilities = [
        "metric_retrieval",
        "trend_comparison",
        "anomaly_detection",
        "dimensional_analysis",
    ]

    INTENT_PRODUCT_MAP = {
        "retention": "retention",  "churn":    "retention",
        "grr":       "retention",  "nrr":      "retention",
        "renewal":   "retention",
        "bookings":  "bookings",   "revenue":  "bookings",
        "arr":       "bookings",   "mrr":      "bookings",
        "ltv":       "ltv",        "lifetime": "ltv",
        "cac":       "cac",        "payback":  "cac",
        "acquisition cost": "cac",
    }

    def __init__(self, config=None, **kwargs):
        # Accept and silently drop legacy enable_mock kwarg
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        if not config or not config.databricks.host:
            raise EnvironmentError(
                "InformationAgent requires DATABRICKS_HOST, "
                "DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH to be set."
            )
        self._connector = DatabricksConnector(config.databricks)

    def _detect_products(self, query: str) -> List[str]:
        query_lower = query.lower()
        products = set()
        for keyword, product in self.INTENT_PRODUCT_MAP.items():
            if keyword in query_lower:
                products.add(product)
        return list(products) if products else ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._detect_products(request.query)
        time_range = request.time_range or "last_month"

        all_metrics: Dict[str, Any] = {}
        sources: List[str] = []
        anomalies: List[str] = []

        for product in products:
            metrics = self._fetch_live(product, time_range)
            sources.append(DATA_PRODUCTS.get(product, {}).get("table", product))
            all_metrics[product] = metrics
            anomalies.extend(self._detect_anomalies(product, metrics))

        summary = self._build_summary(all_metrics, anomalies, time_range)
        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"metrics": all_metrics, "anomalies": anomalies},
            summary=summary,
            sources=sources,
            confidence=0.95,
            metadata={"products_queried": products, "time_range": time_range},
        )

    def _fetch_live(self, product: str, time_range: str) -> Dict:
        info = DATA_PRODUCTS.get(product, {})
        table = info.get("table", product)
        sql = f"""
            SELECT * FROM {table}
            WHERE period = '{time_range}'
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = self._connector.query(sql)
        return rows[0] if rows else {}

    def _detect_anomalies(self, product: str, metrics: Dict) -> List[str]:
        anomalies = []
        if product == "retention":
            grr = metrics.get("gross_retention_rate", 100)
            if grr < 85:
                anomalies.append(
                    f"⚠️ GRR ({grr}%) below 85% threshold — "
                    f"investigate churn drivers immediately."
                )
            at_risk = metrics.get("at_risk_accounts", 0)
            if at_risk > 30:
                anomalies.append(
                    f"⚠️ {at_risk} accounts at-risk — CS outreach required."
                )
        if product == "cac":
            payback = metrics.get("payback_period_months", 0)
            if payback > 20:
                anomalies.append(
                    f"⚠️ CAC payback ({payback}mo) exceeds 20-month target."
                )
        if product == "bookings":
            vs_t = metrics.get("bookings_vs_target_pct", 0)
            if vs_t < -5:
                anomalies.append(f"⚠️ Bookings {abs(vs_t)}% below target.")
        return anomalies

    def _build_summary(
        self, all_metrics: Dict, anomalies: List[str], time_range: str
    ) -> str:
        parts = [f"📊 **Metrics Summary** ({time_range})"]
        for product, metrics in all_metrics.items():
            parts.append(f"\n**{product.upper()}**")
            for k, v in metrics.items():
                if k in ("time_range", "breakdown", "ltv_by_segment"):
                    continue
                label = k.replace("_", " ").title()
                parts.append(f"  • {label}: {v}")
        if anomalies:
            parts.append("\n**🚨 Anomalies:**")
            parts.extend(f"  {a}" for a in anomalies)
        return "\n".join(parts)
