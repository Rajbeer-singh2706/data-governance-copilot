"""Information Agent — delegates to IDataService."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest, AgentResult, BaseAgent

_PRODUCT_KEYWORDS = {
    "retention": ["retention", "grr", "nrr", "churn", "customer"],
    "bookings": ["bookings", "arr", "revenue", "sales"],
    "cac": ["cac", "acquisition", "cost", "marketing"],
    "ltv": ["ltv", "lifetime", "value"],
}
_THRESHOLDS = {
    "retention": {"gross_retention_rate": 85.0, "grr": 85.0, "churn_rate": 15.0,
                  "at_risk_accounts": 30},
    "bookings": {"arr": 0},
    "cac": {"payback_months": 36},
    "ltv": {"ltv_cac_ratio": 3.0},
}


class InformationAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "information_agent"

    def __init__(self, config=None, data_service=None):
        from services.factory import get_data_service
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
            if field in ("gross_retention_rate", "grr") and value < threshold:
                anomalies.append(
                    f"{product}: GRR {value}% is below threshold {threshold}% — risk of missing targets"
                )
            elif field == "churn_rate" and value > threshold:
                anomalies.append(
                    f"{product}: churn rate {value}% exceeds threshold {threshold}%"
                )
            elif field == "at_risk_accounts" and value > threshold:
                anomalies.append(
                    f"{product}: {value} at-risk accounts exceeds alert threshold {threshold} — high at-risk count"
                )
            elif field == "payback_months" and threshold > 0 and value > threshold:
                anomalies.append(
                    f"{product}: CAC payback {value} months exceeds {threshold}-month limit"
                )
            elif field == "ltv_cac_ratio" and value < threshold:
                anomalies.append(
                    f"{product}: LTV:CAC ratio {value} is below {threshold}x minimum"
                )
        return anomalies

    def execute(self, request: AgentRequest) -> AgentResult:
        import time
        t0 = time.monotonic()
        try:
            products = request.data_products or self._detect_products(request.query)
            all_metrics: Dict[str, Dict] = {}
            all_anomalies: List[str] = []

            for product in products:
                metrics = self._fetch_metrics(product, request.time_range)
                all_metrics[product] = metrics
                all_anomalies.extend(self._detect_anomalies(product, metrics))

            elapsed = (time.monotonic() - t0) * 1000
            return AgentResult(
                success=True,
                data={"metrics": all_metrics, "anomalies": all_anomalies},
                message=f"Retrieved metrics for {len(products)} products",
                confidence=0.95,
                sources=[f"analytics.{p}" for p in products],
                metadata={"products_queried": products, "anomaly_count": len(all_anomalies)},
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            return AgentResult.failure(f"InformationAgent error: {exc}", str(exc))
