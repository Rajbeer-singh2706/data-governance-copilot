from typing import Any, Dict, List, Optional
from core.base_agent import BaseAgent, AgentRequest, AgentResult

# ── Mock Collibra data ───────────────────────────────────
MOCK_COLLIBRA_ASSETS = {
    "retention": {
        "asset_id":       "col-ret-001",
        "asset_name":     "Gross Retention Rate",
        "asset_type":     "Business Metric",
        "domain":         "Customer Success",
        "status":         "Accepted",
        "owner":          "Jane Smith (VP Customer Success)",
        "steward":        "Data Governance Team",
        "classification": ["KPI", "Confidential", "PII-Free"],
        "certified":      True,
        "data_quality": {
            "overall_score": 72,
            "completeness":  68,
            "accuracy":      81,
            "timeliness":    74,
            "consistency":   69,
            "validity":      77,
            "uniqueness":    98,
            "last_assessed": "2024-09-28",
            "issues": [
                {
                    "dimension":   "completeness",
                    "description": "EU region data missing for 3 days "
                                   "(2024-09-12 to 2024-09-14)",
                    "severity":    "High",
                    "status":      "Open",
                },
                {
                    "dimension":   "consistency",
                    "description": "Discrepancy between CRM and DWH "
                                   "for 7 churned accounts",
                    "severity":    "Medium",
                    "status":      "In Progress",
                },
            ],
        },
        "lineage": {
            "source_systems":   ["Salesforce CRM", "Zuora Billing"],
            "etl_pipeline":     "databricks_retention_pipeline_v3",
            "last_refresh":     "2024-10-01T06:00:00Z",
            "refresh_schedule": "Daily 6:00 UTC",
            "target_tables":    [
                "analytics.retention_metrics",
                "marts.cs_kpis",
            ],
        },
    },
    "bookings": {
        "asset_id":       "col-bkn-001",
        "asset_name":     "Total Bookings",
        "asset_type":     "Business Metric",
        "domain":         "Revenue Operations",
        "status":         "Accepted",
        "owner":          "Mike Johnson (RevOps Director)",
        "steward":        "Revenue Analytics Team",
        "classification": ["KPI", "Highly Confidential"],
        "certified":      True,
        "data_quality": {
            "overall_score": 88,
            "completeness":  92,
            "accuracy":      89,
            "timeliness":    95,
            "consistency":   84,
            "validity":      91,
            "uniqueness":    99,
            "last_assessed": "2024-10-01",
            "issues":        [],
        },
        "lineage": {
            "source_systems":   ["Salesforce CRM"],
            "etl_pipeline":     "databricks_bookings_pipeline_v5",
            "last_refresh":     "2024-10-01T04:00:00Z",
            "refresh_schedule": "Daily 4:00 UTC",
            "target_tables":    [
                "analytics.bookings_fact",
                "marts.finance_kpis",
            ],
        },
    },
    "cac": {
        "asset_id":       "col-cac-001",
        "asset_name":     "Customer Acquisition Cost",
        "asset_type":     "Business Metric",
        "domain":         "Marketing Analytics",
        "status":         "Accepted",
        "owner":          "Sarah Lee (Marketing Analytics Lead)",
        "steward":        "Marketing Analytics Team",
        "certified":      True,
        "classification": ["KPI", "Confidential"],
        "data_quality": {
            "overall_score": 79,
            "completeness":  83,
            "accuracy":      78,
            "timeliness":    81,
            "consistency":   74,
            "validity":      82,
            "uniqueness":    97,
            "last_assessed": "2024-09-30",
            "issues": [
                {
                    "dimension":   "consistency",
                    "description": "Agency spend data delayed by "
                                   "5 business days each month",
                    "severity":    "Medium",
                    "status":      "Known Issue",
                },
            ],
        },
        "lineage": {
            "source_systems": [
                "Salesforce CRM", "Marketo",
                "Google Ads",     "LinkedIn Ads",
            ],
            "etl_pipeline":     "databricks_marketing_pipeline_v2",
            "last_refresh":     "2024-10-01T05:00:00Z",
            "refresh_schedule": "Daily 5:00 UTC",
            "target_tables":    ["analytics.cac_metrics"],
        },
    },
    "ltv": {
        "asset_id":       "col-ltv-001",
        "asset_name":     "Customer Lifetime Value",
        "asset_type":     "Business Metric",
        "domain":         "Data Science",
        "status":         "Accepted",
        "owner":          "Priya Nair (Head of Data Science)",
        "steward":        "Data Science Team",
        "certified":      True,
        "classification": ["KPI", "Confidential"],
        "data_quality": {
            "overall_score": 84,
            "completeness":  88,
            "accuracy":      82,
            "timeliness":    79,
            "consistency":   85,
            "validity":      88,
            "uniqueness":    96,
            "last_assessed": "2024-09-29",
            "issues":        [],
        },
        "lineage": {
            "source_systems": [
                "Databricks Feature Store",
                "Zuora Billing",
            ],
            "etl_pipeline":     "ds_ltv_model_pipeline_v4",
            "last_refresh":     "2024-10-01T02:00:00Z",
            "refresh_schedule": "Weekly Sunday 2:00 UTC",
            "target_tables":    ["analytics.customer_ltv"],
        },
    },
}


# ── Metadata Agent ───────────────────────────────────────
class MetadataAgent(BaseAgent):
    """
    Retrieves governance metadata from Collibra DGC.
    Mock mode: returns MOCK_COLLIBRA_ASSETS dict.
    Production: calls Collibra REST API.
    """
    name         = "metadata_agent"
    description  = "Retrieves governance metadata from Collibra"
    capabilities = [
        "data_quality_scores",
        "ownership_stewardship",
        "lineage_tracing",
        "classification_retrieval",
    ]

    PRODUCT_ALIASES = {
        "retention": "retention", "churn":   "retention",
        "grr":       "retention", "nrr":     "retention",
        "bookings":  "bookings",  "revenue": "bookings",
        "arr":       "bookings",
        "cac":       "cac",       "payback": "cac",
        "ltv":       "ltv",
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return list({
            v for k, v in self.PRODUCT_ALIASES.items()
            if k in q
        }) or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        products = (
            request.data_products
            or self._resolve_products(request.query)
        )
        results = {}
        sources = []

        for product in products:
            if self.enable_mock:
                asset = MOCK_COLLIBRA_ASSETS.get(product)
                if asset:
                    results[product] = asset
                    sources.append(
                        f"Collibra DGC: {asset['asset_name']}"
                    )

        if not results:
            return AgentResult(
                agent_name = self.name,
                success    = True,
                summary    = "No governance metadata found "
                             "for this query.",
                confidence = 0.5,
            )

        summary    = self._build_summary(results)
        overall_dq = self._compute_overall_dq(results)

        return AgentResult(
            agent_name = self.name,
            success    = True,
            data       = results,
            summary    = summary,
            sources    = sources,
            confidence = 0.93,
            metadata   = {
                "overall_dq_score": overall_dq,
                "products":         products,
            },
        )

    def _dq_icon(self, score: int) -> str:
        if score >= 85: return "🟢"
        if score >= 70: return "🟡"
        return "🔴"

    def _compute_overall_dq(self,
                              results: Dict) -> Optional[float]:
        scores = [
            r.get("data_quality", {}).get("overall_score")
            for r in results.values()
            if isinstance(r.get("data_quality"), dict)
        ]
        return round(sum(scores) / len(scores), 1) \
               if scores else None

    def _build_summary(self, results: Dict) -> str:
        if not results:
            return "No governance metadata found."

        parts = ["🏛️ **Governance & Metadata**"]
        for product, asset in results.items():
            name = asset.get("asset_name", product.upper())
            cert = "✅" if asset.get("certified") else "⚠️"
            parts.append(f"\n**{name}** {cert}")
            parts.append(
                f"  • Owner: {asset.get('owner', 'Unknown')}"
            )
            parts.append(
                f"  • Steward: {asset.get('steward', 'Unknown')}"
            )
            parts.append(
                f"  • Classifications: "
                f"{', '.join(asset.get('classification', []))}"
            )

            dq = asset.get("data_quality", {})
            if dq:
                score = dq.get("overall_score", 0)
                icon  = self._dq_icon(score)
                parts.append(
                    f"  • DQ Score: {icon} {score}/100"
                )
                parts.append(
                    f"    ↳ Completeness:{dq.get('completeness')} "
                    f"| Accuracy:{dq.get('accuracy')} "
                    f"| Timeliness:{dq.get('timeliness')}"
                )
                issues = dq.get("issues", [])
                if issues:
                    parts.append(
                        f"  • Open DQ Issues ({len(issues)}):"
                    )
                    for issue in issues:
                        sev  = issue["severity"]
                        sicon = "🔴" if sev == "High" else "🟡"
                        parts.append(
                            f"    {sicon} [{sev}] "
                            f"{issue['description']}"
                        )

            lineage = asset.get("lineage", {})
            if lineage:
                parts.append(
                    f"  • Sources: "
                    f"{', '.join(lineage.get('source_systems', []))}"
                )
                parts.append(
                    f"  • Last Refresh: "
                    f"{lineage.get('last_refresh', 'Unknown')}"
                )
                parts.append(
                    f"  • Schedule: "
                    f"{lineage.get('refresh_schedule', 'Unknown')}"
                )

        return "\n".join(parts)