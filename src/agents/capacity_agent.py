"""
src/agents/capacity_agent.py

Fetches Jira issues and creates tickets via Jira REST API.
When USE_MCP=true, uses MCP tools instead.
Requires JIRA_BASE_URL, JIRA_API_TOKEN, JIRA_EMAIL, JIRA_PROJECT_KEY env vars.
"""
import os
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult


class JiraClient:
    """Thin Jira REST v3 client."""

    def __init__(self):
        self.base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        self.email = os.getenv("JIRA_EMAIL", "")
        self.token = os.getenv("JIRA_API_TOKEN", "")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "DATA")
        if not self.base_url or not self.token or not self.email:
            raise EnvironmentError(
                "CapacityAgent requires JIRA_BASE_URL, JIRA_EMAIL, "
                "and JIRA_API_TOKEN environment variables."
            )

    def _auth(self):
        from requests.auth import HTTPBasicAuth
        return HTTPBasicAuth(self.email, self.token)

    def _headers(self) -> Dict:
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def search_issues(self, jql: str, max_results: int = 20) -> List[Dict]:
        import requests
        url = f"{self.base_url}/rest/api/3/search"
        payload = {"jql": jql, "maxResults": max_results,
                   "fields": ["summary", "status", "priority", "issuetype",
                               "assignee", "created", "updated", "labels",
                               "description"]}
        resp = requests.post(url, json=payload, auth=self._auth(),
                             headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def create_issue(self, summary: str, description: str,
                     issue_type: str, priority: str,
                     labels: List[str]) -> Dict:
        import requests
        url = f"{self.base_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project":     {"key": self.project_key},
                "summary":     summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": description}
                    ]}],
                },
                "issuetype": {"name": issue_type},
                "priority":  {"name": priority},
                "labels":    labels,
            }
        }
        resp = requests.post(url, json=payload, auth=self._auth(),
                             headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()


_PRODUCT_KEYWORDS = {
    "retention": ["retention", "churn", "grr", "nrr"],
    "bookings":  ["bookings", "revenue", "arr", "mrr"],
    "cac":       ["cac", "marketing", "acquisition"],
    "ltv":       ["ltv", "lifetime"],
}


class CapacityAgent(BaseAgent):
    """
    Fetches Jira issues and creates tickets.
    Uses MCP tools when USE_MCP=true, otherwise direct REST API.
    """
    name = "capacity_agent"
    description = "Fetches Jira issues and creates tickets"
    capabilities = [
        "issue_retrieval",
        "incident_tracking",
        "blocker_identification",
        "ticket_creation",
    ]

    def __init__(self, config=None, **kwargs):
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        from core.mcp_client import get_mcp_tools
        self._mcp_tools = get_mcp_tools("jira")
        if not self._mcp_tools:
            self._client = JiraClient()
        else:
            self._client = None

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return [p for p, kws in _PRODUCT_KEYWORDS.items()
                if any(k in q for k in kws)] or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        is_write = any(
            kw in request.query.lower()
            for kw in ["create ticket", "open bug", "raise issue",
                       "log incident", "create a bug", "file a ticket"]
        )
        return self._handle_create(request) if is_write else self._handle_read(request)

    def _handle_read(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        all_issues: Dict[str, List] = {}
        sources: List[str] = []

        for product in products:
            issues = self._fetch_issues(product)
            all_issues[product] = issues
            sources.append(f"Jira: {product.upper()}")

        open_count = sum(
            1 for issues in all_issues.values()
            for i in issues
            if i.get("status") in ("Open", "In Progress")
        )
        summary = self._build_read_summary(all_issues)
        return AgentResult(
            agent_name=self.name,
            success=True,
            data=all_issues,
            summary=summary,
            sources=sources,
            confidence=0.90,
            metadata={"open_issues": open_count, "products": products},
        )

    def _fetch_issues(self, product: str) -> List[Dict]:
        if self._mcp_tools:
            return self._fetch_via_mcp(product)
        return self._fetch_via_rest(product)

    def _fetch_via_rest(self, product: str) -> List[Dict]:
        project_key = os.getenv("JIRA_PROJECT_KEY", "DATA")
        jql = (f'project = "{project_key}" AND labels = "{product}" '
               f'ORDER BY updated DESC')
        raw_issues = self._client.search_issues(jql)
        return [
            {
                "id":      i["key"],
                "type":    i["fields"]["issuetype"]["name"],
                "priority": i["fields"]["priority"]["name"],
                "status":  i["fields"]["status"]["name"],
                "summary": i["fields"]["summary"],
                "assignee": (i["fields"].get("assignee") or {}).get("emailAddress", "Unassigned"),
                "labels":  i["fields"].get("labels", []),
            }
            for i in raw_issues
        ]

    def _fetch_via_mcp(self, product: str) -> List[Dict]:
        try:
            search_tool = next(
                (t for t in self._mcp_tools if "search" in t.name.lower()), None
            )
            if not search_tool:
                return []
            raw = search_tool.run({"query": f"label:{product}"})
            return raw if isinstance(raw, list) else []
        except Exception as exc:
            self.logger.warning("Jira MCP fetch failed for %s: %s", product, exc)
            return []

    def _handle_create(self, request: AgentRequest) -> AgentResult:
        context = request.context
        summary = context.get(
            "ticket_summary",
            f"Auto-detected issue: {request.query[:80]}"
        )
        description = context.get("ticket_description", request.query)
        issue_type = context.get("issue_type", "Bug")
        priority = context.get("priority", "Medium")
        labels = context.get("labels", ["auto-generated", "data-governance"])

        ticket = self._create_ticket(summary, description, issue_type, priority, labels)
        ticket_id = ticket.get("key", "UNKNOWN")

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=(
                f"✅ Jira {issue_type} created: **{ticket_id}**\n   {summary}"
            ),
            data={
                "ticket_id": ticket_id,
                "type":      issue_type,
                "summary":   summary,
                "priority":  priority,
                "status":    "Open",
                "labels":    labels,
            },
            sources=["Jira"],
            confidence=0.95,
        )

    def _create_ticket(self, summary: str, description: str,
                       issue_type: str, priority: str,
                       labels: List[str]) -> Dict:
        if self._mcp_tools:
            create_tool = next(
                (t for t in self._mcp_tools if "create" in t.name.lower()), None
            )
            if create_tool:
                return create_tool.run({
                    "summary": summary, "description": description,
                    "issuetype": issue_type, "priority": priority,
                    "labels": labels,
                })
        return self._client.create_issue(summary, description, issue_type,
                                         priority, labels)

    def create_ticket_from_anomaly(
        self,
        anomaly_description: str,
        product: str,
        priority: str = "High",
    ) -> AgentResult:
        """Convenience method called by auto_ticket_node."""
        request = AgentRequest(
            query=f"create ticket for {product} data quality issue",
            context={
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
                "labels": ["auto-dq-alert", product, "data-governance"],
            },
            data_products=[product],
        )
        return self.execute(request)

    def _build_read_summary(self, all_issues: Dict) -> str:
        parts = ["🎫 **Jira Issues & Operational Status**"]
        total_open = 0
        for product, issues in all_issues.items():
            if not issues:
                parts.append(f"\n**{product.upper()}** — No open issues ✅")
                continue
            open_issues = [i for i in issues
                           if i.get("status") in ("Open", "In Progress")]
            total_open += len(open_issues)
            parts.append(
                f"\n**{product.upper()}** — "
                f"{len(open_issues)} open / {len(issues)} total"
            )
            for issue in issues:
                status = issue.get("status", "Unknown")
                prio = issue.get("priority", "Medium")
                itype = issue.get("type", "Issue")
                picon = {"High": "🔴", "Critical": "🚨",
                         "Medium": "🟡", "Low": "🟢"}.get(prio, "⚪")
                sicon = {"Done": "✅", "In Progress": "🔄",
                         "Open": "🔴", "Known Issue": "📌"}.get(status, "⚪")
                parts.append(
                    f"  {picon} **{issue['id']}** [{itype}] {sicon} {status}\n"
                    f"     {issue['summary']}"
                )
        if total_open == 0:
            parts.append("\n✅ No open issues found.")
        else:
            parts.append(f"\n_Total open: {total_open}_")
        return "\n".join(parts)
