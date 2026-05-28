"""
src/services/databricks/mock.py
Mock Databricks service — returns realistic canned data for dev / CI.

No network calls, no credentials required.
Satisfies IDataService protocol.

Data is keyed on table name so queries to different analytics tables
get different but consistent results across calls.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


# ── Canned metric rows per analytics table ─────────────────────────────────
_MOCK_DATA: Dict[str, List[Dict[str, Any]]] = {
    "analytics.retention_metrics": [
        {
            "period":                "last_month",
            "gross_retention_rate":  88.4,
            "net_retention_rate":    104.2,
            "churn_rate":            2.1,
            "at_risk_accounts":      12,
            "renewed_accounts":      423,
            "churned_accounts":      9,
        }
    ],
    "analytics.bookings_fact": [
        {
            "period":                   "last_month",
            "total_bookings":           4_250_000,
            "net_new_bookings":         820_000,
            "expansion_bookings":       310_000,
            "bookings_vs_target_pct":   3.2,
            "arr":                      51_000_000,
        }
    ],
    "analytics.cac_metrics": [
        {
            "period":                "last_month",
            "blended_cac":           8_400,
            "payback_period_months": 14,
            "sales_cac":             11_200,
            "marketing_cac":         5_600,
        }
    ],
    "analytics.customer_ltv": [
        {
            "period":        "last_month",
            "avg_ltv":       72_000,
            "ltv_cac_ratio": 8.6,
            "ltv_by_segment": {
                "enterprise": 210_000,
                "mid_market":  58_000,
                "smb":         18_000,
            },
        }
    ],
    # rule evaluation — CASE WHEN expressions land here when table is unknown
    "default": [{"result": 1}],
}

# Anomaly scenario: GRR below threshold (used in HITL tests)
_LOW_GRR_SCENARIO: Dict[str, Any] = {
    "period":                "last_month",
    "gross_retention_rate":  78.0,   # below 85% threshold → triggers anomaly
    "net_retention_rate":    91.0,
    "churn_rate":            7.5,
    "at_risk_accounts":      47,     # above 30 → second anomaly
    "renewed_accounts":      310,
    "churned_accounts":      28,
}


class MockDatabricksService:
    """
    In-memory mock satisfying IDataService.
    Parses the FROM clause to choose which canned table to return.
    """

    def __init__(self, low_grr: bool = False) -> None:
        """
        Args:
            low_grr: If True, retention rows trigger anomaly detection
                     (used in integration / HITL tests).
        """
        self._low_grr = low_grr

    # ── IDataService ──────────────────────────────────────────────────────

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Return canned rows for the table referenced in FROM clause."""
        table = self._extract_table(sql)
        rows  = self._get_rows(table)
        return rows

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_table(sql: str) -> str:
        """Best-effort parse of 'FROM <table>' from a SQL string."""
        match = re.search(r"\bFROM\s+([\w.]+)", sql, re.IGNORECASE)
        return match.group(1).lower() if match else "default"

    def _get_rows(self, table: str) -> List[Dict[str, Any]]:
        rows = _MOCK_DATA.get(table, _MOCK_DATA["default"])
        if table == "analytics.retention_metrics" and self._low_grr:
            return [_LOW_GRR_SCENARIO]
        return rows