"""
src/services/collibra/real.py
Real Collibra DGC REST API client.

Requires env vars:
  COLLIBRA_BASE_URL, COLLIBRA_USERNAME, COLLIBRA_PASSWORD
  (or COLLIBRA_API_TOKEN for token-based auth)

Raises EnvironmentError at construction if credentials are missing.
Satisfies IMetadataService protocol.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


class CollibraService:
    """
    Thin wrapper around Collibra REST API v1.
    Satisfies IMetadataService protocol.
    """

    def __init__(self) -> None:
        self._base_url = os.getenv("COLLIBRA_BASE_URL", "").rstrip("/")
        self._username = os.getenv("COLLIBRA_USERNAME", "")
        self._password = os.getenv("COLLIBRA_PASSWORD", "")
        self._token    = os.getenv("COLLIBRA_API_TOKEN", "")

        if not self._base_url or not (
            self._token or (self._username and self._password)
        ):
            raise EnvironmentError(
                "CollibraService requires COLLIBRA_BASE_URL and either "
                "COLLIBRA_API_TOKEN or COLLIBRA_USERNAME + COLLIBRA_PASSWORD."
            )

        self._session = self._build_session()

    # ── Internal ──────────────────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        if self._token:
            s.headers.update({"Authorization": f"Bearer {self._token}"})
        else:
            s.auth = (self._username, self._password)
        s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        return s

    def _get(self, path: str, params: Dict = None) -> Any:
        resp = self._session.get(
            f"{self._base_url}/rest/2.0{path}",
            params=params or {},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ── IMetadataService ───────────────────────────────────────────────────

    def search_assets(self, name: str) -> List[Dict]:
        """Search for data assets by name. Returns list of asset dicts."""
        data = self._get("/assets", params={"name": name, "nameMatchMode": "ANYWHERE"})
        return data.get("results", [])

    def get_asset(self, asset_id: str) -> Dict:
        """Fetch a single asset by UUID."""
        return self._get(f"/assets/{asset_id}")

    def get_data_quality(self, asset_id: str) -> Dict:
        """Return DQ metrics for an asset. Maps to Collibra's metrics endpoint."""
        results = self._get(
            "/dataQualityRuleResults",
            params={"assetId": asset_id, "limit": 50},
        )
        rules = results.get("results", [])
        passed  = sum(1 for r in rules if r.get("passed"))
        failed  = len(rules) - passed
        score   = round((passed / len(rules)) * 100, 1) if rules else 0.0
        return {
            "asset_id":    asset_id,
            "total_rules": len(rules),
            "passed":      passed,
            "failed":      failed,
            "score":       score,
            "rules":       rules,
        }