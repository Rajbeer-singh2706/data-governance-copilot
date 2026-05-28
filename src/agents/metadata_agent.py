"""
src/agents/metadata_agent.py

Retrieves governance metadata via IMetadataService.
All Collibra-specific REST / MCP logic lives in services/collibra/.
This agent only owns:
  - product alias resolution
  - summary & DQ score formatting
"""
from typing import Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.mcp_client import get_mcp_tools
from services.base import IMetadataService
from services.factory import get_metadata_service


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
    Retrieves governance metadata via IMetadataService.
    In mock mode: MockCollibraService (no credentials needed).
    In prod mode: CollibraService (requires COLLIBRA_* env vars).
    MCP tools (USE_MCP=true) are layered on top when available.
    """
    name = "metadata_agent"
    description = "Retrieves governance metadata from Collibra"
    capabilities = [
        "data_quality_scores",
        "ownership_stewardship",
        "lineage_tracing",
        "classification_retrieval",
    ]

    def __init__(
        self,
        config=None,
        metadata_service: Optional[IMetadataService] = None,
        **kwargs,
    ) -> None:
        """
        Args:
            config:           AppConfig
            metadata_service: Explicit IMetadataService injection (useful in tests)
        """
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        self._svc: IMetadataService = metadata_service or get_metadata_service(config)
        self._mcp_tools = get_mcp_tools("collibra")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return list({v for k, v in _PRODUCT_ALIASES.items() if k in q}) or ["retention"]

    def _fetch_asset(self, product: str) -> Optional[Dict]:
        search_name = _PRODUCT_SEARCH_NAMES.get(product, product)

        # MCP takes priority when enabled
        if self._mcp_tools:
            return self._fetch_via_mcp(search_name, product)

        try:
            assets = self._svc.search_assets(search_name)
            if not assets:
                return None
            asset    = assets[0]
            asset_id = asset.get("id", "")
            dq_data  = {}
            try:
                dq_data = self._svc.get_data_quality(asset_id)
            except Exception:
                pass
            return {
                "asset_id":     asset_id,
                "asset_name":   asset.get("name", search_name),
                "asset_type":   asset.get("type", "Business Metric"),
                "domain":       asset.get("domain", ""),
                "status":       asset.get("status", "Unknown"),
                "owner":        asset.get("owner", ""),
                "steward":      asset.get("steward", ""),
                "data_quality": dq_data,
            }
        except Exception as exc:
            self.logger.warning("Collibra fetch failed for %s: %s", product, exc)
            return None

    def _fetch_via_mcp(self, search_name: str, product: str) -> Optional[Dict]:
        try:
            tool = next(
                (t for t in self._mcp_tools if "search" in t.name.lower()), None
            )
            if not tool:
                return None
            raw = tool.run({"name": search_name})
            return {"asset_name": search_name, "raw": raw}
        except Exception as exc:
            self.logger.warning("Collibra MCP fetch failed for %s: %s", product, exc)
            return None

    # ── IAgent ────────────────────────────────────────────────────────────

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        results: Dict[str, Dict] = {}
        sources: List[str]       = []

        for product in products:
            asset = self._fetch_asset(product)
            if asset:
                results[product] = asset
                sources.append(f"Collibra DGC: {asset.get('asset_name', product)}")

        if not results:
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary="No governance metadata found for this query.",
                confidence=0.5,
            )

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=results,
            summary=self._build_summary(results),
            sources=sources,
            confidence=0.93,
            metadata={
                "overall_dq_score": self._compute_overall_dq(results),
                "products": products,
            },
        )

    # ── Summary formatting ────────────────────────────────────────────────

    @staticmethod
    def _dq_icon(score: float) -> str:
        if score >= 85: return "🟢"
        if score >= 70: return "🟡"
        return "🔴"

    def _compute_overall_dq(self, results: Dict) -> Optional[float]:
        scores = [
            r["data_quality"].get("score")
            for r in results.values()
            if isinstance(r.get("data_quality"), dict)
            and r["data_quality"].get("score") is not None
        ]
        return round(sum(scores) / len(scores), 1) if scores else None

    def _build_summary(self, results: Dict) -> str:
        parts = ["🏛️ **Governance & Metadata**"]
        for product, asset in results.items():
            name   = asset.get("asset_name", product.upper())
            status = asset.get("status", "Unknown")
            parts.append(f"\n**{name}** — Status: {status}")
            if asset.get("owner"):
                parts.append(f"  • Owner: {asset['owner']}")
            if asset.get("steward"):
                parts.append(f"  • Steward: {asset['steward']}")
            if asset.get("domain"):
                parts.append(f"  • Domain: {asset['domain']}")
            dq = asset.get("data_quality", {})
            if dq and isinstance(dq, dict):
                score = dq.get("score") or dq.get("overall_score")
                if score is not None:
                    parts.append(f"  • DQ Score: {self._dq_icon(score)} {score}/100")
                if dq.get("failed", 0):
                    parts.append(f"  • Failed Rules: {dq['failed']}/{dq.get('total_rules', '?')}")
        return "\n".join(parts)