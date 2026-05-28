"""
src/services/collibra/mock.py
Mock Collibra service — canned governance metadata for dev / CI.

No network calls, no credentials required.
Satisfies IMetadataService protocol.
"""
from __future__ import annotations

from typing import Dict, List


_MOCK_ASSETS: Dict[str, Dict] = {
    "retention": {
        "id":          "asset-001",
        "name":        "Customer Retention Metrics",
        "type":        "Data Set",
        "owner":       "Customer Success",
        "steward":     "Alice Chen",
        "domain":      "Analytics",
        "status":      "Accepted",
        "description": "Monthly retention KPIs including GRR, NRR and churn rate.",
        "tags":        ["retention", "kpi", "monthly"],
        "last_updated": "2024-01-10",
    },
    "bookings": {
        "id":          "asset-002",
        "name":        "Bookings Fact Table",
        "type":        "Data Set",
        "owner":       "Revenue Operations",
        "steward":     "Bob Smith",
        "domain":      "Analytics",
        "status":      "Accepted",
        "description": "Net-new and expansion bookings, ARR, and vs-target tracking.",
        "tags":        ["bookings", "revenue", "arr"],
        "last_updated": "2024-01-11",
    },
    "cac": {
        "id":          "asset-003",
        "name":        "CAC Metrics",
        "type":        "Data Set",
        "owner":       "Marketing Analytics",
        "steward":     "Carol Davis",
        "domain":      "Analytics",
        "status":      "Accepted",
        "description": "Blended, sales, and marketing customer acquisition cost.",
        "tags":        ["cac", "marketing", "cost"],
        "last_updated": "2024-01-09",
    },
    "ltv": {
        "id":          "asset-004",
        "name":        "Customer LTV",
        "type":        "Data Set",
        "owner":       "Data Science",
        "steward":     "Dan Lee",
        "domain":      "Analytics",
        "status":      "Accepted",
        "description": "Average LTV, LTV:CAC ratio, and segment breakdown.",
        "tags":        ["ltv", "cohort", "data-science"],
        "last_updated": "2024-01-12",
    },
}

_MOCK_DQ: Dict[str, Dict] = {
    "asset-001": {"asset_id": "asset-001", "total_rules": 8, "passed": 7, "failed": 1, "score": 87.5},
    "asset-002": {"asset_id": "asset-002", "total_rules": 6, "passed": 6, "failed": 0, "score": 100.0},
    "asset-003": {"asset_id": "asset-003", "total_rules": 5, "passed": 4, "failed": 1, "score": 80.0},
    "asset-004": {"asset_id": "asset-004", "total_rules": 7, "passed": 5, "failed": 2, "score": 71.4},
}


class MockCollibraService:
    """
    In-memory Collibra mock satisfying IMetadataService.
    """

    # ── IMetadataService ───────────────────────────────────────────────────

    def search_assets(self, name: str) -> List[Dict]:
        """Return assets whose name or tags contain the search term."""
        name_lower = name.lower()
        results = []
        for key, asset in _MOCK_ASSETS.items():
            if (
                name_lower in asset["name"].lower()
                or name_lower in key
                or any(name_lower in t for t in asset.get("tags", []))
            ):
                results.append(asset)
        # If nothing matched, return all assets (broad search fallback)
        return results if results else list(_MOCK_ASSETS.values())

    def get_asset(self, asset_id: str) -> Dict:
        """Fetch by asset UUID."""
        for asset in _MOCK_ASSETS.values():
            if asset["id"] == asset_id:
                return asset
        return {"id": asset_id, "name": "Unknown Asset", "status": "Not Found"}

    def get_data_quality(self, asset_id: str) -> Dict:
        """Return canned DQ metrics for the asset."""
        return _MOCK_DQ.get(
            asset_id,
            {"asset_id": asset_id, "total_rules": 0, "passed": 0, "failed": 0, "score": 0.0},
        )