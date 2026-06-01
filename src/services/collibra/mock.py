"""Mock Collibra service — canned assets + DQ scores."""
from __future__ import annotations

from typing import Dict, List

_ASSETS = {
    "asset-001": {"id": "asset-001", "name": "retention_metrics", "domain": "Customer Success",
                  "status": "Approved", "owner": "cs-team@company.com",
                  "steward": "data-steward@company.com"},
    "asset-002": {"id": "asset-002", "name": "bookings_fact", "domain": "Revenue Operations",
                  "status": "Approved", "owner": "revops@company.com",
                  "steward": "data-steward@company.com"},
    "asset-003": {"id": "asset-003", "name": "cac_metrics", "domain": "Marketing Analytics",
                  "status": "Approved", "owner": "marketing@company.com",
                  "steward": "data-steward@company.com"},
    "asset-004": {"id": "asset-004", "name": "customer_ltv", "domain": "Data Science",
                  "status": "Approved", "owner": "ds@company.com",
                  "steward": "data-steward@company.com"},
}
_DQ = {
    "asset-001": {"score": 94.2, "passed": 47, "failed": 3, "total_rules": 50},
    "asset-002": {"score": 98.0, "passed": 49, "failed": 1, "total_rules": 50},
    "asset-003": {"score": 88.5, "passed": 40, "failed": 5, "total_rules": 45},
    "asset-004": {"score": 91.0, "passed": 41, "failed": 4, "total_rules": 45},
}
_NAME_MAP = {
    "retention": "asset-001", "bookings": "asset-002",
    "cac": "asset-003", "ltv": "asset-004", "customer_ltv": "asset-004",
}


class MockCollibraService:
    def search_assets(self, name: str) -> List[Dict]:
        name_lower = name.lower()
        for keyword, asset_id in _NAME_MAP.items():
            if keyword in name_lower:
                return [_ASSETS[asset_id]]
        return list(_ASSETS.values())

    def get_asset(self, asset_id: str) -> Dict:
        # Return a fallback dict with id so callers always get a usable dict
        return _ASSETS.get(asset_id, {"id": asset_id, "name": "unknown", "status": "unknown"})

    def get_data_quality(self, asset_id: str) -> Dict:
        return _DQ.get(asset_id, {"score": 0, "passed": 0, "failed": 0, "total_rules": 0})
