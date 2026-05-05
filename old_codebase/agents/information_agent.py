"""
Information Agent
-----------------
Queries structured data sources (Databricks, SQL Data Warehouse) to retrieve
metrics, dimensions, and data lineage for enterprise data products.

Supports: Bookings, Retention, LTV, CAC and any registered data product.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from config.settings import DATA_PRODUCTS


# ---------------------------------------------------------------------------
# Mock data generators (used when ENABLE_MOCK=true or connection unavailable)
# ---------------------------------------------------------------------------

def _mock_retention_metrics(time_range: str) -> Dict:
    base = 87.3
    delta = random.uniform(-4.5, -1.2)
    return {
        "gross_retention_rate": round(base + delta, 2),
        "gross_retention_prev": round(base, 2),
        "net_retention_rate": round(107.4 + random.uniform(-6, -2), 2),
        "churn_rate": round(100 - (base + delta), 2),
        "churned_accounts": random.randint(18, 34),
        "total_accounts": 412,
        "at_risk_accounts": random.randint(22, 41),
        "time_range": time_range or "last_month",
        "breakdown": {
            "Enterprise": round(93.1 + random.uniform(-2, 0.5), 2),
            "Mid-Market": round(88.7 + random.uniform(-3, -0.5), 2),
            "SMB": round(79.2 + random.uniform(-5, -1), 2),
        },
    }


def _mock_bookings_metrics(time_range: str) -> Dict:
    return {
        "total_bookings_usd": round(random.uniform(4_200_000, 5_100_000), 0),
        "net_new_bookings_usd": round(random.uniform(1_800_000, 2_400_000), 0),
        "expansion_bookings_usd": round(random.uniform(900_000, 1_300_000), 0),
        "renewal_bookings_usd": round(random.uniform(1_400_000, 1_900_000), 0),
        "bookings_vs_target_pct": round(random.uniform(-8, 12), 1),
        "time_range": time_range or "last_month",
    }


def _mock_cac_metrics(time_range: str) -> Dict:
    return {
        "blended_cac_usd": round(random.uniform(8_200, 11_500), 0),
        "paid_cac_usd": round(random.uniform(14_000, 19_000), 0),
        "organic_cac_usd": round(random.uniform(3_500, 6_000), 0),
        "payback_period_months": round(random.uniform(14, 22), 1),
        "cac_vs_prev_pct": round(random.uniform(-5, 15), 1),
        "time_range": time_range or "last_month",
    }


def _mock_ltv_metrics(time_range: str) -> Dict:
    return {
        "avg_ltv_usd": round(random.uniform(45_000, 75_000), 0),
        "ltv_cac_ratio": round(random.uniform(3.2, 5.8), 2),
        "ltv_by_segment": {
            "Enterprise": round(random.uniform(180_000, 280_000), 0),
            "Mid-Market": round(random.uniform(55_000, 90_000), 0),
            "SMB": round(random.uniform(18_000, 32_000), 0),
        },
        "time_range": time_range or "last_month",
    }


MOCK_GENERATORS = {
    "retention": _mock_retention_metrics,
    "bookings": _mock_bookings_metrics,
    "cac": _mock_cac_metrics,
    "ltv": _mock_ltv_metrics,
}


# ---------------------------------------------------------------------------
# Databricks connector (real implementation)
# ---------------------------------------------------------------------------

class DatabricksConnector:
    """Thin wrapper around Databricks SQL connector."""

    def __init__(self, config):
        self.config = config
        self._connection = None

    def connect(self):
        try:
            from databricks import sql
            self._connection = sql.connect(
                server_hostname=self.config.host,
                http_path=self.config.http_path,
                access_token=self.config.token,
            )
        except ImportError:
            raise ImportError("Install 'databricks-sql-connector' for Databricks support.")

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


# ---------------------------------------------------------------------------
# Information Agent
# ---------------------------------------------------------------------------

class InformationAgent(BaseAgent):
    """
    Fetches structured metrics and data from SQL/Databricks for registered data products.

    Read capabilities:
    - Metric retrieval (current period vs prior period)
    - Dimensional breakdowns (segment, region, cohort)
    - Data lineage tracing
    - Anomaly flagging based on threshold rules
    """

    name = "information_agent"
    description = "Queries structured data sources for metrics and facts"
    capabilities = [
        "metric_retrieval",
        "dimensional_analysis",
        "trend_comparison",
        "data_lineage",
        "anomaly_detection",
    ]

    # Map intent keywords → data products
    INTENT_PRODUCT_MAP = {
        "retention": "retention",
        "churn": "retention",
        "renewal": "retention",
        "bookings": "bookings",
        "revenue": "bookings",
        "arr": "bookings",
        "mrr": "bookings",
        "ltv": "ltv",
        "lifetime value": "ltv",
        "cac": "cac",
        "acquisition cost": "cac",
        "payback": "cac",
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)
        self._connector = None
        if config and not enable_mock:
            self._connector = DatabricksConnector(config.databricks)

    def _detect_products(self, query: str) -> List[str]:
        """Identify which data products are relevant to the query."""
        query_lower = query.lower()
        products = set()
        for keyword, product in self.INTENT_PRODUCT_MAP.items():
            if keyword in query_lower:
                products.add(product)
        # Fallback: if nothing detected, check explicit product list
        if not products:
            for product in DATA_PRODUCTS:
                if product in query_lower:
                    products.add(product)
        return list(products) if products else ["retention"]  # sensible default

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._detect_products(request.query)
        time_range = request.time_range or "last_month"

        all_metrics: Dict[str, Any] = {}
        sources: List[str] = []
        anomalies: List[str] = []

        for product in products:
            if self.enable_mock or not self._connector:
                metrics = self._fetch_mock(product, time_range)
                sources.append(f"[MOCK] {DATA_PRODUCTS.get(product, {}).get('table', product)}")
            else:
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
            confidence=0.95 if not self.enable_mock else 0.85,
            metadata={"products_queried": products, "time_range": time_range},
        )

    def _fetch_mock(self, product: str, time_range: str) -> Dict:
        generator = MOCK_GENERATORS.get(product)
        return generator(time_range) if generator else {"error": f"No mock data for {product}"}

    def _fetch_live(self, product: str, time_range: str) -> Dict:
        product_info = DATA_PRODUCTS.get(product, {})
        table = product_info.get("table", product)
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
                    f"⚠️ Gross Retention Rate ({grr}%) is below the 85% threshold — investigate churn drivers."
                )
            at_risk = metrics.get("at_risk_accounts", 0)
            if at_risk > 30:
                anomalies.append(
                    f"⚠️ {at_risk} accounts flagged as at-risk — requires immediate CS outreach."
                )
        if product == "cac":
            payback = metrics.get("payback_period_months", 0)
            if payback > 20:
                anomalies.append(
                    f"⚠️ CAC payback period ({payback} months) exceeds 20-month target."
                )
        if product == "bookings":
            vs_target = metrics.get("bookings_vs_target_pct", 0)
            if vs_target < -5:
                anomalies.append(
                    f"⚠️ Bookings are {abs(vs_target)}% below target this period."
                )
        return anomalies

    def _build_summary(self, all_metrics: Dict, anomalies: List[str], time_range: str) -> str:
        parts = [f"📊 **Data Metrics Summary** ({time_range})"]
        for product, metrics in all_metrics.items():
            parts.append(f"\n**{product.upper()}**")
            for k, v in metrics.items():
                if k in ("time_range", "breakdown", "ltv_by_segment"):
                    continue
                parts.append(f"  • {k.replace('_', ' ').title()}: {v}")
        if anomalies:
            parts.append("\n**🚨 Anomalies Detected:**")
            parts.extend(f"  {a}" for a in anomalies)
        return "\n".join(parts)
