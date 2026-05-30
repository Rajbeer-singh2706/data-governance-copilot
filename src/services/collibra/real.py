"""Real Collibra REST service."""
from __future__ import annotations

import os
from typing import Dict, List

import requests


class CollibraService:
    def __init__(self):
        self.base_url = os.getenv("COLLIBRA_BASE_URL", "")
        self.username = os.getenv("COLLIBRA_USERNAME", "")
        self.password = os.getenv("COLLIBRA_PASSWORD", "")
        if not all([self.base_url, self.username, self.password]):
            raise EnvironmentError("COLLIBRA_BASE_URL, COLLIBRA_USERNAME, COLLIBRA_PASSWORD required")
        self._auth = (self.username, self.password)

    def search_assets(self, name: str) -> List[Dict]:
        resp = requests.get(
            f"{self.base_url}/rest/2.0/assets",
            params={"name": name, "nameMatchMode": "ANYWHERE", "limit": 10},
            auth=self._auth, timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_asset(self, asset_id: str) -> Dict:
        resp = requests.get(f"{self.base_url}/rest/2.0/assets/{asset_id}",
                            auth=self._auth, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_data_quality(self, asset_id: str) -> Dict:
        resp = requests.get(
            f"{self.base_url}/rest/2.0/dataQuality/rules",
            params={"assetId": asset_id}, auth=self._auth, timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        passed = sum(1 for r in results if r.get("status") == "PASSED")
        failed = len(results) - passed
        score = (passed / len(results) * 100) if results else 0
        return {"score": round(score, 1), "passed": passed, "failed": failed, "total_rules": len(results)}
