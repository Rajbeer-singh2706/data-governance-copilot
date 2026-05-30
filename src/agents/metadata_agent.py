"""Metadata Agent — delegates to IMetadataService."""
from __future__ import annotations

from typing import Optional

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent
from src.core.mcp_client import get_mcp_tools

_ALIASES = {
    "churn": "retention", "arr": "bookings", "revenue": "bookings",
    "acquisition": "cac", "ltv": "ltv", "lifetime": "ltv",
}


class MetadataAgent(BaseAgent):
    def __init__(self, config=None, metadata_service=None):
        from src.services.factory import get_metadata_service
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

            return AgentResult(
                success=True,
                data=metadata,
                message=f"Retrieved metadata for {len(metadata)} assets",
                confidence=0.93,
                sources=[f"collibra://{v['asset_id']}" for v in metadata.values() if v.get("asset_id")],
                metadata={"assets_found": len(metadata)},
            )
        except Exception as exc:
            return AgentResult.failure(f"MetadataAgent error: {exc}", str(exc))
