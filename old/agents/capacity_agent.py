"""
Capacity Agent
--------------
Integrates with Jira to fetch and create tickets related to data products.

READ:  Fetch stories, bugs, incidents for a given data product or time period.
WRITE: Create Jira tickets (bug, story, task) based on detected issues.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.logging_utils import logger, with_retry


# ---------------------------------------------------------------------------
# Mock Jira data
# ---------------------------------------------------------------------------

MOCK_JIRA_ISSUES = {
    "retention": [
        {
            "id": "DATA-4821",
            "type": "Bug",
            "priority": "High",
            "status": "In Progress",
            "summary": "EU region retention data missing — pipeline failure in Databricks job",
            "description": (
                "The `retention_etl_eu` Databricks job failed between 2024-09-12 and 2024-09-14 "
                "due to a schema change in the Salesforce source table. 3 days of EU data "
                "are missing from analytics.retention_metrics."
            ),
            "assignee": "data-eng-eu@company.com",
            "reporter": "data-governance@company.com",
            "created": "2024-09-15T09:00:00Z",
            "updated": "2024-10-01T14:22:00Z",
            "labels": ["data-quality", "retention", "etl-failure"],
            "components": ["Retention Pipeline", "EU Data"],
        },
        {
            "id": "DATA-4890",
            "type": "Bug",
            "priority": "Medium",
            "status": "Open",
            "summary": "GRR/NRR discrepancy between Salesforce CRM and Data Warehouse",
            "description": (
                "7 accounts show different churn status between CRM and DWH. "
                "Root cause: delayed Salesforce sync for multi-entity contracts."
            ),
            "assignee": "data-eng-core@company.com",
            "reporter": "cs-analytics@company.com",
            "created": "2024-09-28T11:30:00Z",
            "updated": "2024-09-30T09:15:00Z",
            "labels": ["data-quality", "retention", "crm-sync"],
            "components": ["CRM Integration"],
        },
        {
            "id": "DATA-4712",
            "type": "Story",
            "priority": "Medium",
            "status": "Done",
            "summary": "Add at-risk account segmentation to retention dashboard",
            "description": "Implement early warning scoring for accounts likely to churn in next 90 days.",
            "assignee": "data-eng-core@company.com",
            "reporter": "cs-analytics@company.com",
            "created": "2024-08-10T08:00:00Z",
            "updated": "2024-09-20T16:00:00Z",
            "labels": ["feature", "retention", "dashboard"],
            "components": ["Retention Dashboard"],
        },
    ],
    "bookings": [
        {
            "id": "DATA-4955",
            "type": "Story",
            "priority": "High",
            "status": "In Progress",
            "summary": "Migrate bookings pipeline to new Salesforce API v55",
            "description": "Salesforce deprecating API v40. Migration required by Q4 2024.",
            "assignee": "data-eng-revops@company.com",
            "reporter": "revops@company.com",
            "created": "2024-09-01T10:00:00Z",
            "updated": "2024-10-01T11:00:00Z",
            "labels": ["migration", "bookings", "salesforce"],
            "components": ["Bookings Pipeline"],
        },
    ],
    "cac": [
        {
            "id": "DATA-4801",
            "type": "Bug",
            "priority": "Medium",
            "status": "Known Issue",
            "summary": "Agency spend data delayed by 5 business days (LinkedIn/Google Ads)",
            "description": (
                "Third-party ad agency invoices are processed manually, causing a 5-day lag "
                "in CAC calculations for months end."
            ),
            "assignee": "data-eng-marketing@company.com",
            "reporter": "marketing-analytics@company.com",
            "created": "2024-07-15T09:00:00Z",
            "updated": "2024-09-01T10:00:00Z",
            "labels": ["known-issue", "cac", "marketing"],
            "components": ["CAC Pipeline"],
        },
    ],
}


# ---------------------------------------------------------------------------
# Jira REST API connector
# ---------------------------------------------------------------------------

class JiraConnector:
    """Jira Cloud REST API v3 client."""

    def __init__(self, config):
        self.base_url = config.base_url.rstrip("/")
        self.auth = (config.email, config.api_token)
        self.project_key = config.project_key
        self.default_assignee = config.default_assignee
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    @with_retry(max_retries=3)
    def search_issues(self, jql: str, max_results: int = 10) -> List[Dict]:
        resp = self.session.post(
            f"{self.base_url}/rest/api/3/issue/picker",
            json={"jql": jql, "maxResults": max_results, "fields": ["summary", "status", "priority", "assignee", "description", "labels"]},
        )
        resp.raise_for_status()
        return resp.json().get("issues", [])

    @with_retry(max_retries=3)
    def create_issue(self, issue_type: str, summary: str, description: str, priority: str = "Medium", labels: List[str] = None) -> Dict:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                },
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "labels": labels or [],
            }
        }
        if self.default_assignee:
            payload["fields"]["assignee"] = {"accountId": self.default_assignee}

        resp = self.session.post(f"{self.base_url}/rest/api/3/issue", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Capacity Agent
# ---------------------------------------------------------------------------

class CapacityAgent(BaseAgent):
    """
    Jira-integrated capacity and operations agent.

    READ:
    - Fetch open bugs, stories, incidents related to data products
    - Identify current blockers and delays

    WRITE:
    - Create Bug, Story, or Task tickets in Jira
    - Auto-generate tickets from detected data quality issues
    """

    name = "capacity_agent"
    description = "Fetches and creates Jira tickets for data product operations"
    capabilities = [
        "issue_retrieval",
        "incident_tracking",
        "blocker_identification",
        "ticket_creation",
        "auto_triage",
    ]

    PRODUCT_KEYWORDS = {
        "retention": ["retention", "churn", "grr", "nrr", "renewal"],
        "bookings": ["bookings", "revenue", "arr", "contract"],
        "cac": ["cac", "marketing", "acquisition"],
        "ltv": ["ltv", "lifetime"],
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)
        self._connector = None
        if config and not enable_mock:
            self._connector = JiraConnector(config.jira)

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return [p for p, kws in self.PRODUCT_KEYWORDS.items() if any(k in q for k in kws)] or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        is_create = any(
            kw in request.query.lower()
            for kw in ["create ticket", "open bug", "raise issue", "log incident", "create story", "create task"]
        )

        if is_create:
            return self._handle_create(request)
        else:
            return self._handle_read(request)

    def _handle_read(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        all_issues: Dict[str, List] = {}
        sources: List[str] = []

        for product in products:
            if self.enable_mock or not self._connector:
                issues = MOCK_JIRA_ISSUES.get(product, [])
                sources.append(f"Jira (Mock): {product.upper()}")
            else:
                jql = f'project = {self._connector.project_key} AND labels = "{product}" ORDER BY created DESC'
                issues = self._connector.search_issues(jql)
                sources.append(f"Jira: {product.upper()}")
            all_issues[product] = issues

        summary = self._build_read_summary(all_issues)
        open_count = sum(
            1 for issues in all_issues.values()
            for i in issues
            if i.get("status") in ("Open", "In Progress")
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=all_issues,
            summary=summary,
            sources=sources,
            confidence=0.90,
            metadata={"open_issues": open_count, "products": products},
        )

    def _handle_create(self, request: AgentRequest) -> AgentResult:
        """Auto-create a Jira ticket based on the user's request or a detected issue."""
        query = request.query
        context = request.context

        # Derive ticket details from context or query
        summary = context.get("ticket_summary", f"Auto-detected issue: {query[:80]}")
        description = context.get("ticket_description", query)
        issue_type = context.get("issue_type", "Bug")
        priority = context.get("priority", "Medium")
        labels = context.get("labels", ["auto-generated", "data-governance"])

        if self.enable_mock or not self._connector:
            fake_id = f"DATA-{5000 + hash(summary) % 1000}"
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary=f"✅ [MOCK] Jira {issue_type} created: **{fake_id}** — {summary}",
                data={
                    "ticket_id": fake_id,
                    "type": issue_type,
                    "summary": summary,
                    "status": "Open",
                    "mock": True,
                },
                sources=["Jira (Mock)"],
            )

        result = self._connector.create_issue(issue_type, summary, description, priority, labels)
        ticket_id = result.get("key", "UNKNOWN")
        ticket_url = f"{self._connector.base_url}/browse/{ticket_id}"

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"✅ Jira {issue_type} created: **{ticket_id}** — {summary}\n🔗 {ticket_url}",
            data={"ticket_id": ticket_id, "url": ticket_url, "type": issue_type},
            sources=["Jira"],
        )

    def _build_read_summary(self, all_issues: Dict[str, List]) -> str:
        parts = ["🎫 **Jira Issues & Operational Status**"]
        total_open = 0

        for product, issues in all_issues.items():
            if not issues:
                continue
            open_issues = [i for i in issues if i.get("status") in ("Open", "In Progress")]
            total_open += len(open_issues)
            parts.append(f"\n**{product.upper()}** — {len(open_issues)} open / {len(issues)} total")

            for issue in issues:
                status = issue.get("status", "Unknown")
                prio = issue.get("priority", "Medium")
                itype = issue.get("type", "Issue")
                prio_icon = {"High": "🔴", "Critical": "🚨", "Medium": "🟡", "Low": "🟢"}.get(prio, "⚪")
                status_icon = {"Done": "✅", "In Progress": "🔄", "Open": "🔴", "Known Issue": "📌"}.get(status, "⚪")
                parts.append(
                    f"  {prio_icon} **{issue['id']}** [{itype}] {status_icon} {status}\n"
                    f"     {issue['summary']}"
                )

        if total_open == 0:
            parts.append("\n✅ No open issues found for queried data products.")
        else:
            parts.append(f"\n_Total open issues: {total_open}_")

        return "\n".join(parts)

    def create_ticket_from_anomaly(self, anomaly_description: str, product: str, priority: str = "High") -> AgentResult:
        """Convenience method: create a Jira bug from an automatically detected anomaly."""
        request = AgentRequest(
            query=f"create ticket for data quality issue in {product}",
            context={
                "ticket_summary": f"[Auto-DQ] {product.upper()}: {anomaly_description[:100]}",
                "ticket_description": (
                    f"Automated data quality alert detected by Data Governance Copilot.\n\n"
                    f"Product: {product}\nAnomaly: {anomaly_description}\n\n"
                    f"Please investigate and resolve."
                ),
                "issue_type": "Bug",
                "priority": priority,
                "labels": ["auto-dq-alert", product, "data-governance"],
            },
            data_products=[product],
        )
        return self.execute(request)
