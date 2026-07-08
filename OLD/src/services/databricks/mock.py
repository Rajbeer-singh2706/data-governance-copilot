"""Mock Databricks service with canned analytics rows."""
from __future__ import annotations

import re
from typing import Dict, List

_RETENTION_NORMAL = [
    {"product": "retention", "gross_retention_rate": 92.5, "grr": 92.5,
     "nrr": 108.3, "churn_rate": 7.5, "active_customers": 1240, "period": "2024-Q1",
     "at_risk_accounts": 12},
]
_RETENTION_LOW = [
    {"product": "retention", "gross_retention_rate": 78.0, "grr": 78.0,
     "nrr": 95.1, "churn_rate": 22.0, "active_customers": 980, "period": "2024-Q1",
     "at_risk_accounts": 87},
]
_BOOKINGS = [
    {"product": "bookings", "arr": 4_200_000, "total_bookings": 4_200_000,
     "new_bookings": 380_000, "expansion": 120_000, "churn_value": 45_000, "period": "2024-Q1"},
]
_CAC = [
    {"product": "cac", "blended_cac": 2850, "sales_cac": 3100,
     "marketing_cac": 2600, "payback_months": 14, "period": "2024-Q1"},
]
_LTV = [
    {"product": "ltv", "avg_ltv": 38_500, "ltv_cac_ratio": 13.5,
     "median_ltv": 32_000, "p90_ltv": 72_000, "period": "2024-Q1"},
]

_TABLE_MAP = {
    "retention_metrics": _RETENTION_NORMAL,
    "bookings_fact": _BOOKINGS,
    "cac_metrics": _CAC,
    "customer_ltv": _LTV,
}


class MockDatabricksService:
    def __init__(self, low_grr: bool = False):
        self._low_grr = low_grr

    def query(self, sql: str) -> List[Dict]:
        match = re.search(r"FROM\s+\w+\.(\w+)", sql, re.IGNORECASE)
        table = match.group(1).lower() if match else ""
        if "retention" in table:
            return _RETENTION_LOW if self._low_grr else _RETENTION_NORMAL
        for key, rows in _TABLE_MAP.items():
            if key in table:
                return rows
        return [{"result": "no data", "sql": sql}]
