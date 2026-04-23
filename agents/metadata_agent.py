"""
Metadata Agent
--------------
Integrates with Collibra (Data Governance Center) via MCP/REST API.

READ:  Fetch business metadata, data quality scores, ownership, classifications.
WRITE: Update metadata, create business terms, update governance attributes.
"""

import json
import random
from typing import Any, Dict, List, Optional
from datetime import datetime

import requests

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.logging_utils import logger, with_retry


# ---------------------------------------------------------------------------
# Mock Collibra data
# ---------------------------------------------------------------------------

MOCK_COLLIBRA_ASSETS = {
    "retention": {
        "asset_id": "col-ret-001",
        "asset_name": "Gross Retention Rate",
        "asset_type": "Business Metric",
        "domain": "Customer Success",
        "status": "Accepted",
        "owner": "Jane Smith (VP Customer Success)",
        "steward": "Data Governance Team",
        "classification": ["KPI", "Confidential", "PII-Free"],
        "business_term": "GRR — % of ARR retained from existing customers, excluding expansions.",
        "certified": True,
        "data_quality": {
            "overall_score": 72,
            "completeness": 68,
            "accuracy": 81,
            "timeliness": 74,
            "consistency": 69,
            "validity": 77,
            "uniqueness": 98,
            "last_assessed": "2024-09-28",
            "issues": [
                {
                    "dimension": "completeness",
                    "description": "EU region data missing for 3 days (2024-09-12 to 2024-09-14)",
                    "severity": "High",
                    "status": "Open",
                },
                {
                    "dimension": "consistency",
                    "description": "Discrepancy between CRM and DWH for 7 churned accounts",
                    "severity": "Medium",
                    "status": "In Progress",
                },
            ],
        },
        "lineage": {
            "source_systems": ["Salesforce CRM", "Zuora Billing"],
            "etl_pipeline": "databricks_retention_pipeline_v3",
            "last_refresh": "2024-10-01T06:00:00Z",
            "refresh_schedule": "Daily 6:00 UTC",
            "target_tables": ["analytics.retention_metrics", "marts.cs_kpis"],
        },
    },
    "bookings": {
        "asset_id": "col-bkn-001",
        "asset_name": "Total Bookings",
        "asset_type": "Business Metric",
        "domain": "Revenue Operations",
        "status": "Accepted",
        "owner": "Mike Johnson (RevOps Director)",
        "steward": "Revenue Analytics Team",
        "classification": ["KPI", "Highly Confidential"],
        "certified": True,
        "data_quality": {
            "overall_score": 88,
            "completeness": 92,
            "accuracy": 89,
            "timeliness": 95,
            "consistency": 84,
            "validity": 91,
            "uniqueness": 99,
            "last_assessed": "2024-10-01",
            "issues": [],
        },
        "lineage": {
            "source_systems": ["Salesforce CRM"],
            "etl_pipeline": "databricks_bookings_pipeline_v5",
            "last_refresh": "2024-10-01T04:00:00Z",
            "refresh_schedule": "Daily 4:00 UTC",
            "target_tables": ["analytics.bookings_fact", "marts.finance_kpis"],
        },
    },
    "cac": {
        "asset_id": "col-cac-001",
        "asset_name": "Customer Acquisition Cost",
        "asset_type": "Business Metric",
        "domain": "Marketing Analytics",
        "status": "Accepted",
        "owner": "Sarah Lee (Marketing Analytics Lead)",
        "steward": "Marketing Analytics Team",
        "certified": True,
        "classification": ["KPI", "Confidential"],
        "data_quality": {
            "overall_score": 79,
            "completeness": 83,
            "accuracy": 78,
            "timeliness": 81,
            "consistency": 74,
            "validity": 82,
            "uniqueness": 97,
            "last_assessed": "2024-09-30",
            "issues": [
                {
                    "dimension": "consistency",
                    "description": "Agency spend data delayed by 5 business days each month",
                    "severity": "Medium",
                    "status": "Known Issue",
                },
            ],
        },
        "lineage": {
            "source_systems": ["Salesforce CRM", "Marketo", "Google Ads", "LinkedIn Ads"],
            "etl_pipeline": "databricks_marketing_pipeline_v2",
            "last_refresh": "2024-10-01T05:00:00Z",
            "refresh_schedule": "Daily 5:00 UTC",
            "target_tables": ["analytics.cac_metrics"],
        },
    },
}


# ---------------------------------------------------------------------------
# Collibra REST API connector
# ---------------------------------------------------------------------------

class CollibraConnector:
    """
    Collibra DGC REST API client.
    Supports: asset search, data quality retrieval, attribute updates.
    """

    def __init__(self, config):
        self.base_url = config.base_url.rstrip("/")
        self.auth = (config.username, config.password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Content-Type": "application/json"})

    @with_retry(max_retries=3)
    def get_asset(self, asset_name: str) -> Optional[Dict]:
        resp = self.session.get(
            f"{self.base_url}/rest/2.0/assets",
            params={"name": asset_name, "nameMatchMode": "EXACT", "limit": 1},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["results"][0] if data.get("results") else None

    @with_retry(max_retries=3)
    def get_data_quality(self, asset_id: str) -> Dict:
        resp = self.session.get(
            f"{self.base_url}/rest/2.0/assets/{asset_id}/attributes"
        )
        resp.raise_for_status()
        return resp.json()

    @with_retry(max_retries=3)
    def update_attribute(self, asset_id: str, attribute_type_id: str, value: str) -> bool:
        payload = {"assetId": asset_id, "typeId": attribute_type_id, "value": value}
        resp = self.session.post(f"{self.base_url}/rest/2.0/attributes", json=payload)
        return resp.status_code in (200, 201)

    @with_retry(max_retries=3)
    def create_business_term(self, name: str, definition: str, domain_id: str) -> Dict:
        payload = {
            "name": name,
            "displayName": name,
            "domainId": domain_id,
            "typeId": "00000000-0000-0000-0000-000000031008",  # Business Term type
            "status": {"name": "Draft"},
        }
        resp = self.session.post(f"{self.base_url}/rest/2.0/assets", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Metadata Agent
# ---------------------------------------------------------------------------

class MetadataAgent(BaseAgent):
    """
    Governance metadata agent integrated with Collibra DGC.

    READ:
    - Business metadata (definitions, ownership, stewardship)
    - Data quality scores and dimension breakdowns
    - Classifications, certifications, and governance status
    - Data lineage (sources, pipelines, refresh schedules)

    WRITE:
    - Update business descriptions and classifications
    - Create new business terms
    - Flag data quality issues
    """

    name = "metadata_agent"
    description = "Retrieves and updates governance metadata via Collibra"
    capabilities = [
        "metadata_retrieval",
        "data_quality_scores",
        "ownership_stewardship",
        "lineage_tracing",
        "classification_management",
        "metadata_write",
        "business_term_creation",
    ]

    PRODUCT_ALIASES = {
        "retention": "retention", "churn": "retention", "grr": "retention", "nrr": "retention",
        "bookings": "bookings", "arr": "bookings", "revenue": "bookings",
        "cac": "cac", "acquisition": "cac",
        "ltv": "ltv",
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)
        self._connector = None
        if config and not enable_mock:
            self._connector = CollibraConnector(config.collibra)

    def _resolve_product(self, query: str) -> List[str]:
        q = query.lower()
        return list({v for k, v in self.PRODUCT_ALIASES.items() if k in q}) or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._resolve_product(request.query)

        # Determine if this is a write request
        is_write = any(
            kw in request.query.lower()
            for kw in ["update", "set owner", "classify", "create term", "add definition"]
        )

        if is_write:
            return self._handle_write(request, products)
        else:
            return self._handle_read(request, products)

    def _handle_read(self, request: AgentRequest, products: List[str]) -> AgentResult:
        results: Dict[str, Any] = {}
        sources: List[str] = []

        for product in products:
            if self.enable_mock or not self._connector:
                data = MOCK_COLLIBRA_ASSETS.get(product)
                if not data:
                    continue
                results[product] = data
                sources.append(f"Collibra DGC: {data.get('asset_name', product)}")
            else:
                asset = self._connector.get_asset(product)
                if asset:
                    dq = self._connector.get_data_quality(asset["id"])
                    results[product] = {**asset, "data_quality": dq}
                    sources.append(f"Collibra DGC: {asset.get('name', product)}")

        summary = self._build_read_summary(results)
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

    def _handle_write(self, request: AgentRequest, products: List[str]) -> AgentResult:
        """Execute a metadata write operation (update attribute or create term)."""
        if self.enable_mock:
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary=f"✅ [MOCK] Metadata updated for: {', '.join(products)}",
                data={"updated": products, "mock": True},
                sources=["Collibra DGC (Mock)"],
            )
        # Real implementation: parse request to determine attribute + value
        # then call self._connector.update_attribute(...)
        return AgentResult(
            agent_name=self.name,
            success=False,
            error="Write operation requires real Collibra credentials.",
            summary="Metadata write not available in current configuration.",
        )

    def _compute_overall_dq(self, results: Dict) -> Optional[float]:
        scores = [
            r.get("data_quality", {}).get("overall_score")
            for r in results.values()
            if isinstance(r.get("data_quality"), dict)
        ]
        return round(sum(scores) / len(scores), 1) if scores else None

    def _build_read_summary(self, results: Dict) -> str:
        if not results:
            return "No governance metadata found for the requested data products."

        parts = ["🏛️ **Governance & Metadata Insights**"]
        for product, asset in results.items():
            parts.append(f"\n**{asset.get('asset_name', product.upper())}**")
            parts.append(f"  • Owner: {asset.get('owner', 'Unknown')}")
            parts.append(f"  • Steward: {asset.get('steward', 'Unknown')}")
            parts.append(f"  • Status: {asset.get('status', 'Unknown')} {'✅' if asset.get('certified') else '⚠️'}")
            parts.append(f"  • Classifications: {', '.join(asset.get('classification', []))}")

            dq = asset.get("data_quality", {})
            if dq:
                score = dq.get("overall_score", "N/A")
                color = "🟢" if score >= 85 else "🟡" if score >= 70 else "🔴"
                parts.append(f"  • Data Quality Score: {color} {score}/100")
                parts.append(f"    ↳ Completeness: {dq.get('completeness', 'N/A')} | "
                              f"Accuracy: {dq.get('accuracy', 'N/A')} | "
                              f"Timeliness: {dq.get('timeliness', 'N/A')}")

                issues = dq.get("issues", [])
                if issues:
                    parts.append(f"  • **Open DQ Issues ({len(issues)}):**")
                    for issue in issues:
                        sev_icon = "🔴" if issue["severity"] == "High" else "🟡"
                        parts.append(f"    {sev_icon} [{issue['severity']}] {issue['description']}")

            lineage = asset.get("lineage", {})
            if lineage:
                parts.append(f"  • Sources: {', '.join(lineage.get('source_systems', []))}")
                parts.append(f"  • Last Refresh: {lineage.get('last_refresh', 'Unknown')}")

        return "\n".join(parts)
