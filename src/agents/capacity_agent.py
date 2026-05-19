# src/agents/capacity_agent.py

from typing import Any, Dict, List, Optional
from core.base_agent import BaseAgent, AgentRequest, AgentResult


# ── Mock Jira data ───────────────────────────────────────
MOCK_JIRA_ISSUES = {
    "retention": [
        {
            "id":          "DATA-4821",
            "type":        "Bug",
            "priority":    "High",
            "status":      "In Progress",
            "summary":     "EU region retention data missing — "
                           "pipeline failure in Databricks job",
            "description": (
                "The retention_etl_eu job failed between "
                "2024-09-12 and 2024-09-14 due to a schema "
                "change in the Salesforce source table. "
                "3 days of EU data are missing."
            ),
            "assignee": "data-eng-eu@company.com",
            "created":  "2024-09-15T09:00:00Z",
            "updated":  "2024-10-01T14:22:00Z",
            "labels":   ["data-quality", "retention",
                         "etl-failure"],
        },
        {
            "id":          "DATA-4890",
            "type":        "Bug",
            "priority":    "Medium",
            "status":      "Open",
            "summary":     "GRR/NRR discrepancy between "
                           "Salesforce and Data Warehouse",
            "description": (
                "7 accounts show different churn status "
                "between CRM and DWH. Root cause: delayed "
                "Salesforce sync for multi-entity contracts."
            ),
            "assignee": "data-eng-core@company.com",
            "created":  "2024-09-28T11:30:00Z",
            "updated":  "2024-09-30T09:15:00Z",
            "labels":   ["data-quality", "retention",
                         "crm-sync"],
        },
        {
            "id":       "DATA-4712",
            "type":     "Story",
            "priority": "Medium",
            "status":   "Done",
            "summary":  "Add at-risk account segmentation "
                        "to retention dashboard",
            "assignee": "data-eng-core@company.com",
            "created":  "2024-08-10T08:00:00Z",
            "updated":  "2024-09-20T16:00:00Z",
            "labels":   ["feature", "retention", "dashboard"],
        },
    ],
    "bookings": [
        {
            "id":          "DATA-4955",
            "type":        "Story",
            "priority":    "High",
            "status":      "In Progress",
            "summary":     "Migrate bookings pipeline to "
                           "Salesforce API v55",
            "description": "Salesforce deprecating API v40. "
                           "Migration required by Q4 2024.",
            "assignee":    "data-eng-revops@company.com",
            "created":     "2024-09-01T10:00:00Z",
            "updated":     "2024-10-01T11:00:00Z",
            "labels":      ["migration", "bookings",
                            "salesforce"],
        },
    ],
    "cac": [
        {
            "id":          "DATA-4801",
            "type":        "Bug",
            "priority":    "Medium",
            "status":      "Known Issue",
            "summary":     "Agency spend data delayed by "
                           "5 business days",
            "description": "Third-party ad agency invoices "
                           "processed manually — 5-day lag.",
            "assignee":    "data-eng-marketing@company.com",
            "created":     "2024-07-15T09:00:00Z",
            "updated":     "2024-09-01T10:00:00Z",
            "labels":      ["known-issue", "cac", "marketing"],
        },
    ],
    "ltv": [],
}

# ── Capacity Agent ───────────────────────────────────────
class CapacityAgent(BaseAgent):
    """
    Fetches Jira issues and creates tickets for data products.
    READ:  Returns open bugs, stories, incidents.
    WRITE: Creates Jira tickets from user requests or anomalies.
    """
    name         = "capacity_agent"
    description  = "Fetches Jira issues and creates tickets"
    capabilities = [
        "issue_retrieval",
        "incident_tracking",
        "blocker_identification",
        "ticket_creation",
    ]

    PRODUCT_KEYWORDS = {
        "retention": ["retention", "churn", "grr", "nrr"],
        "bookings":  ["bookings", "revenue", "arr", "mrr"],
        "cac":       ["cac", "marketing", "acquisition"],
        "ltv":       ["ltv", "lifetime"],
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return [
            p for p, kws in self.PRODUCT_KEYWORDS.items()
            if any(k in q for k in kws)
        ] or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        is_write = any(
            kw in request.query.lower()
            for kw in ["create ticket", "open bug",
                       "raise issue", "log incident",
                       "create a bug", "file a ticket"]
        )
        return self._handle_create(request) if is_write \
               else self._handle_read(request)

    def _handle_read(self,
                     request: AgentRequest) -> AgentResult:
        products   = (request.data_products
                      or self._resolve_products(request.query))
        all_issues: Dict[str, List] = {}
        sources:    List[str]       = []

        for product in products:
            if self.enable_mock:
                issues = MOCK_JIRA_ISSUES.get(product, [])
                sources.append(
                    f"Jira (Mock): {product.upper()}"
                )
            all_issues[product] = issues

        open_count = sum(
            1 for issues in all_issues.values()
            for i in issues
            if i.get("status") in ("Open", "In Progress")
        )
        summary = self._build_read_summary(all_issues)

        return AgentResult(
            agent_name = self.name,
            success    = True,
            data       = all_issues,
            summary    = summary,
            sources    = sources,
            confidence = 0.90,
            metadata   = {
                "open_issues": open_count,
                "products":    products,
            },
        )

    def _handle_create(self,
                       request: AgentRequest) -> AgentResult:
        context     = request.context
        summary     = context.get(
            "ticket_summary",
            f"Auto-detected issue: {request.query[:80]}"
        )
        description = context.get(
            "ticket_description", request.query
        )
        issue_type  = context.get("issue_type", "Bug")
        priority    = context.get("priority", "Medium")
        labels      = context.get(
            "labels", ["auto-generated", "data-governance"]
        )

        if self.enable_mock:
            fake_id = f"DATA-{5000 + abs(hash(summary)) % 1000}"
            return AgentResult(
                agent_name = self.name,
                success    = True,
                summary    = (
                    f"✅ [MOCK] Jira {issue_type} created: "
                    f"**{fake_id}**\n   {summary}"
                ),
                data = {
                    "ticket_id": fake_id,
                    "type":      issue_type,
                    "summary":   summary,
                    "priority":  priority,
                    "status":    "Open",
                    "labels":    labels,
                    "mock":      True,
                },
                sources    = ["Jira (Mock)"],
                confidence = 0.90,
            )
        # Production: call Jira REST API here
        return AgentResult(
            agent_name = self.name,
            success    = False,
            error      = "Real Jira credentials not configured.",
            summary    = "Ticket creation requires real Jira setup.",
        )

    def create_ticket_from_anomaly(
        self,
        anomaly_description: str,
        product: str,
        priority: str = "High",
    ) -> AgentResult:
        """
        Convenience method called by the Supervisor automatically
        when InformationAgent detects a threshold violation.
        """
        request = AgentRequest(
            query = (
                f"create ticket for {product} "
                f"data quality issue"
            ),
            context = {
                "ticket_summary": (
                    f"[Auto-DQ] {product.upper()}: "
                    f"{anomaly_description[:100]}"
                ),
                "ticket_description": (
                    f"Automated data quality alert detected "
                    f"by Data Governance Copilot.\n\n"
                    f"Product: {product}\n"
                    f"Anomaly: {anomaly_description}\n\n"
                    f"Please investigate and resolve."
                ),
                "issue_type": "Bug",
                "priority":   priority,
                "labels": [
                    "auto-dq-alert",
                    product,
                    "data-governance",
                ],
            },
            data_products = [product],
        )
        return self.execute(request)

    def _build_read_summary(self,
                             all_issues: Dict) -> str:
        parts      = ["🎫 **Jira Issues & Operational Status**"]
        total_open = 0

        for product, issues in all_issues.items():
            if not issues:
                parts.append(
                    f"\n**{product.upper()}** "
                    f"— No open issues ✅"
                )
                continue

            open_issues = [
                i for i in issues
                if i.get("status") in ("Open", "In Progress")
            ]
            total_open += len(open_issues)
            parts.append(
                f"\n**{product.upper()}** — "
                f"{len(open_issues)} open / "
                f"{len(issues)} total"
            )
            for issue in issues:
                status = issue.get("status", "Unknown")
                prio   = issue.get("priority", "Medium")
                itype  = issue.get("type", "Issue")
                picon  = {
                    "High":     "🔴",
                    "Critical": "🚨",
                    "Medium":   "🟡",
                    "Low":      "🟢",
                }.get(prio, "⚪")
                sicon = {
                    "Done":        "✅",
                    "In Progress": "🔄",
                    "Open":        "🔴",
                    "Known Issue": "📌",
                }.get(status, "⚪")
                parts.append(
                    f"  {picon} **{issue['id']}** "
                    f"[{itype}] {sicon} {status}\n"
                    f"     {issue['summary']}"
                )

        if total_open == 0:
            parts.append("\n✅ No open issues found.")
        else:
            parts.append(
                f"\n_Total open: {total_open}_"
            )

        return "\n".join(parts)
