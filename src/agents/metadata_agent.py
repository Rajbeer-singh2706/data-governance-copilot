"""
src/agents/metadata_agent.py

Retrieves governance metadata from Collibra DGC REST API.
When USE_MCP=true, uses MCP tools instead of direct REST.
Requires COLLIBRA_BASE_URL + COLLIBRA_API_TOKEN env vars.
"""
import os
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult


class CollibraClient:
    """Thin REST client for Collibra Data Governance Center."""

    BASE_PATH = "/rest/2.0"

    def __init__(self):
        self.base_url = os.getenv("COLLIBRA_BASE_URL", "").rstrip("/")
        self.token = os.getenv("COLLIBRA_API_TOKEN", "")
        if not self.base_url or not self.token:
            raise EnvironmentError(
                "MetadataAgent requires COLLIBRA_BASE_URL and "
                "COLLIBRA_API_TOKEN environment variables."
            )

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def search_assets(self, name: str) -> List[Dict]:
        import requests
        url = f"{self.base_url}{self.BASE_PATH}/assets"
        params = {"name": name, "nameMatchMode": "ANYWHERE", "limit": 5}
        resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_asset(self, asset_id: str) -> Dict:
        import requests
        url = f"{self.base_url}{self.BASE_PATH}/assets/{asset_id}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_data_quality(self, asset_id: str) -> Dict:
        import requests
        url = f"{self.base_url}{self.BASE_PATH}/dataQuality/metrics"
        params = {"assetId": asset_id}
        resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()


# Display names to search in Collibra
_PRODUCT_SEARCH_NAMES = {
    "retention": "Gross Retention Rate",
    "bookings":  "Total Bookings",
    "cac":       "Customer Acquisition Cost",
    "ltv":       "Customer Lifetime Value",
}

_PRODUCT_ALIASES = {
    "retention": "retention", "churn":   "retention",
    "grr":       "retention", "nrr":     "retention",
    "bookings":  "bookings",  "revenue": "bookings",
    "arr":       "bookings",
    "cac":       "cac",       "payback": "cac",
    "ltv":       "ltv",
}


class MetadataAgent(BaseAgent):
    """
    Retrieves governance metadata from Collibra DGC.
    Uses MCP tools when USE_MCP=true, otherwise direct REST.
    """
    name = "metadata_agent"
    description = "Retrieves governance metadata from Collibra"
    capabilities = [
        "data_quality_scores",
        "ownership_stewardship",
        "lineage_tracing",
        "classification_retrieval",
    ]

    def __init__(self, config=None, **kwargs):
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        # Try MCP first; fall back to REST client
        from core.mcp_client import get_mcp_tools
        self._mcp_tools = get_mcp_tools("collibra")
        if not self._mcp_tools:
            self._client = CollibraClient()
        else:
            self._client = None

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return list({
            v for k, v in _PRODUCT_ALIASES.items() if k in q
        }) or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        results: Dict[str, Dict] = {}
        sources: List[str] = []

        for product in products:
            asset = self._fetch_asset(product)
            if asset:
                results[product] = asset
                sources.append(f"Collibra DGC: {asset.get('name', product)}")

        if not results:
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary="No governance metadata found for this query.",
                confidence=0.5,
            )

        summary = self._build_summary(results)
        overall_dq = self._compute_overall_dq(results)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=results,
            summary=summary,
            sources=sources,
            confidence=0.93,
            metadata={"overall_dq_score": overall_dq, "products": products},
        )

    def _fetch_asset(self, product: str) -> Optional[Dict]:
        """Fetch asset via MCP tools or REST client."""
        search_name = _PRODUCT_SEARCH_NAMES.get(product, product)

        if self._mcp_tools:
            return self._fetch_via_mcp(search_name, product)
        return self._fetch_via_rest(search_name, product)

    def _fetch_via_rest(self, search_name: str, product: str) -> Optional[Dict]:
        try:
            assets = self._client.search_assets(search_name)
            if not assets:
                return None
            asset = assets[0]
            asset_id = asset.get("id")
            dq_data = {}
            try:
                dq_data = self._client.get_data_quality(asset_id)
            except Exception:
                pass  # DQ endpoint may not be enabled on all Collibra instances
            return {
                "asset_id":   asset_id,
                "asset_name": asset.get("displayName", search_name),
                "asset_type": asset.get("type", {}).get("name", "Business Metric"),
                "domain":     asset.get("domain", {}).get("name", ""),
                "status":     asset.get("status", {}).get("name", "Unknown"),
                "data_quality": dq_data,
                "raw": asset,
            }
        except Exception as exc:
            self.logger.warning("Collibra REST fetch failed for %s: %s", product, exc)
            return None

    def _fetch_via_mcp(self, search_name: str, product: str) -> Optional[Dict]:
        try:
            # Use the first search tool available from the MCP server
            search_tool = next(
                (t for t in self._mcp_tools if "search" in t.name.lower()), None
            )
            if not search_tool:
                return None
            raw = search_tool.run({"name": search_name})
            return {"asset_name": search_name, "raw": raw}
        except Exception as exc:
            self.logger.warning("Collibra MCP fetch failed for %s: %s", product, exc)
            return None

    def _dq_icon(self, score: int) -> str:
        if score >= 85: return "🟢"
        if score >= 70: return "🟡"
        return "🔴"

    def _compute_overall_dq(self, results: Dict) -> Optional[float]:
        scores = [
            r.get("data_quality", {}).get("overall_score")
            for r in results.values()
            if isinstance(r.get("data_quality"), dict)
            and r["data_quality"].get("overall_score") is not None
        ]
        return round(sum(scores) / len(scores), 1) if scores else None

    def _build_summary(self, results: Dict) -> str:
        if not results:
            return "No governance metadata found."
        parts = ["🏛️ **Governance & Metadata**"]
        for product, asset in results.items():
            name = asset.get("asset_name", product.upper())
            status = asset.get("status", "Unknown")
            parts.append(f"\n**{name}** — Status: {status}")
            if asset.get("domain"):
                parts.append(f"  • Domain: {asset['domain']}")
            dq = asset.get("data_quality", {})
            if dq and isinstance(dq, dict):
                score = dq.get("overall_score")
                if score is not None:
                    parts.append(f"  • DQ Score: {self._dq_icon(score)} {score}/100")
        return "\n".join(parts)
