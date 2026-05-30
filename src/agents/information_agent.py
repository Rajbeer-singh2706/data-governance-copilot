"""Information Agent — delegates to IDataService."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent

_PRODUCT_KEYWORDS = {
    "retention": ["retention", "grr", "nrr", "churn", "customer"],
    "bookings": ["bookings", "arr", "revenue", "sales"],
    "cac": ["cac", "acquisition", "cost", "marketing"],
    "ltv": ["ltv", "lifetime", "value"],
}
_THRESHOLDS = {
    "retention": {"grr": 85.0, "churn_rate": 15.0},
    "bookings": {"arr": 0},
    "cac": {"payback_months": 36},
    "ltv": {"ltv_cac_ratio": 3.0},
}


class InformationAgent(BaseAgent):
    def __init__(self, config=None, data_service=None):
        from src.services.factory import get_data_service
        self._svc = data_service or get_data_service(config)

    def _detect_products(self, query: str) -> List[str]:
        q = query.lower()
        found = [p for p, kws in _PRODUCT_KEYWORDS.items() if any(kw in q for kw in kws)]
        return found or list(_PRODUCT_KEYWORDS.keys())

    def _fetch_metrics(self, product: str, time_range: str) -> Dict:
        table_map = {
            "retention": "analytics.retention_metrics",
            "bookings": "analytics.bookings_fact",
            "cac": "analytics.cac_metrics",
            "ltv": "analytics.customer_ltv",
        }
        table = table_map.get(product, "analytics.retention_metrics")
        sql = f"SELECT * FROM {table} WHERE period = '{time_range}' LIMIT 1"
        rows = self._svc.query(sql)
        return rows[0] if rows else {}

    def _detect_anomalies(self, product: str, metrics: Dict) -> List[str]:
        anomalies = []
        thresholds = _THRESHOLDS.get(product, {})
        for field, threshold in thresholds.items():
            value = metrics.get(field)
            if value is None:
                continue
            if field == "grr" and value < threshold:
                anomalies.append(
                    f"{product}: GRR {value}% is below threshold {threshold}% — risk of missing targets"
                )
            elif field == "churn_rate" and value > threshold:
                anomalies.append(
                    f"{product}: churn rate {value}% exceeds threshold {threshold}%"
                )
            elif field == "payback_months" and value > threshold:
                anomalies.append(
                    f"{product}: CAC payback {value} months exceeds {threshold}-month limit"
                )
            elif field == "ltv_cac_ratio" and value < threshold:
                anomalies.append(
                    f"{product}: LTV:CAC ratio {value} is below {threshold}x minimum"
                )
        return anomalies

    def execute(self, request: AgentRequest) -> AgentResult:
        try:
            products = request.data_products or self._detect_products(request.query)
            all_metrics: Dict[str, Dict] = {}
            all_anomalies: List[str] = []

            for product in products:
                metrics = self._fetch_metrics(product, request.time_range)
                all_metrics[product] = metrics
                all_anomalies.extend(self._detect_anomalies(product, metrics))

            return AgentResult(
                success=True,
                data={"metrics": all_metrics, "anomalies": all_anomalies},
                message=f"Retrieved metrics for {len(products)} products",
                confidence=0.95,
                sources=[f"analytics.{p}" for p in products],
                metadata={"products_queried": products, "anomaly_count": len(all_anomalies)},
            )
        except Exception as exc:
            return AgentResult.failure(f"InformationAgent error: {exc}", str(exc))
