"""
src/agents/information_agent.py

Fetches structured metrics from a data service (Databricks or mock).
All service-specific logic lives in services/databricks/.
This agent only owns:
  - product/keyword detection
  - anomaly thresholds
  - summary formatting
"""
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from config.settings import DATA_PRODUCTS
from services.base import IDataService
from services.factory import get_data_service


class InformationAgent(BaseAgent):
    """
    Fetches structured metrics via IDataService.
    In mock mode: MockDatabricksService (no credentials needed).
    In prod mode: DatabricksService (requires DATABRICKS_* env vars).
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
        "retention": "retention", "churn":    "retention",
        "grr":       "retention", "nrr":      "retention",
        "renewal":   "retention",
        "bookings":  "bookings",  "revenue":  "bookings",
        "arr":       "bookings",  "mrr":      "bookings",
        "ltv":       "ltv",       "lifetime": "ltv",
        "cac":       "cac",       "payback":  "cac",
        "acquisition cost": "cac",
    }

    def __init__(
        self,
        config=None,
        data_service: Optional[IDataService] = None,
        **kwargs,
    ) -> None:
        """
        Args:
            config:       AppConfig (used by factory if data_service not provided)
            data_service: Explicit IDataService injection (useful in tests)
        """
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        self._db: IDataService = data_service or get_data_service(config)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _detect_products(self, query: str) -> List[str]:
        query_lower = query.lower()
        products = {
            product
            for keyword, product in self.INTENT_PRODUCT_MAP.items()
            if keyword in query_lower
        }
        return list(products) if products else ["retention"]

    def _fetch_metrics(self, product: str, time_range: str) -> Dict:
        info  = DATA_PRODUCTS.get(product, {})
        table = info.get("table", product)
        sql   = f"""
            SELECT * FROM {table}
            WHERE period = '{time_range}'
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = self._db.query(sql)
        return rows[0] if rows else {}

    def _detect_anomalies(self, product: str, metrics: Dict) -> List[str]:
        anomalies = []
        if product == "retention":
            grr = metrics.get("gross_retention_rate", 100)
            if grr < 85:
                anomalies.append(
                    f"⚠️ GRR ({grr}%) below 85% threshold — "
                    "investigate churn drivers immediately."
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
                parts.append(f"  • {k.replace('_', ' ').title()}: {v}")
        if anomalies:
            parts.append("\n**🚨 Anomalies:**")
            parts.extend(f"  {a}" for a in anomalies)
        return "\n".join(parts)

    # ── IAgent ────────────────────────────────────────────────────────────

    def _execute(self, request: AgentRequest) -> AgentResult:
        products   = request.data_products or self._detect_products(request.query)
        time_range = request.time_range or "last_month"

        all_metrics: Dict[str, Any] = {}
        sources:     List[str]      = []
        anomalies:   List[str]      = []

        for product in products:
            metrics = self._fetch_metrics(product, time_range)
            all_metrics[product] = metrics
            sources.append(DATA_PRODUCTS.get(product, {}).get("table", product))
            anomalies.extend(self._detect_anomalies(product, metrics))

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"metrics": all_metrics, "anomalies": anomalies},
            summary=self._build_summary(all_metrics, anomalies, time_range),
            sources=sources,
            confidence=0.95,
            metadata={"products_queried": products, "time_range": time_range},
        )