"""Metadata Agent — delegates to IMetadataService."""
from __future__ import annotations

import time
from typing import Optional

from core.base_agent import AgentRequest, AgentResult, BaseAgent
from core.mcp_client import get_mcp_tools

_ALIASES = {
    "churn": "retention", "arr": "bookings", "revenue": "bookings",
    "acquisition": "cac", "ltv": "ltv", "lifetime": "ltv",
}


class MetadataAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "metadata_agent"

    def __init__(self, config=None, metadata_service=None):
        from services.factory import get_metadata_service
        self._svc = metadata_service or get_metadata_service(config)
        self._mcp_tools = get_mcp_tools("collibra")

    def _resolve_products(self, query: str):
        q = query.lower()
        products = []
        for alias, product in _ALIASES.items():
            if alias in q and product not in products:
                products.append(product)
        keywords = ["retention", "bookings", "cac", "ltv"]
        for kw in keywords:
            if kw in q and kw not in products:
                products.append(kw)
        return products or keywords

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.monotonic()
        try:
            products = request.data_products or self._resolve_products(request.query)
            metadata = {}

            for product in products:
                assets = self._svc.search_assets(product)
                if not assets:
                    continue
                asset = assets[0]
                asset_id = asset.get("id", "")
                dq = self._svc.get_data_quality(asset_id) if asset_id else {}
                metadata[product] = {
                    "asset_id": asset_id,
                    "asset_name": asset.get("name", ""),
                    "domain": asset.get("domain", ""),
                    "status": asset.get("status", ""),
                    "owner": asset.get("owner", ""),
                    "steward": asset.get("steward", ""),
                    "data_quality": dq,
                }

            assets_found = len(metadata)
            confidence = 0.93 if assets_found > 0 else 0.5
            sources = [
                f"Collibra/{v['asset_name']}"
                for v in metadata.values()
                if v.get("asset_name")
            ]
            elapsed = (time.monotonic() - t0) * 1000
            return AgentResult(
                success=True,
                data=metadata,
                message=f"**Retrieved metadata** for {assets_found} assets",
                confidence=confidence,
                sources=sources,
                metadata={"assets_found": assets_found},
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            return AgentResult.failure(f"MetadataAgent error: {exc}", str(exc))
