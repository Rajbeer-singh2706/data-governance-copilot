"""
src/agents/capacity_agent.py

Fetches Jira issues and creates tickets via ITicketService.
All Jira-specific REST / MCP logic lives in services/jira/.
This agent only owns:
  - product/keyword routing
  - read vs write dispatch
  - summary formatting
  - create_ticket_from_anomaly convenience method (called by auto_ticket_node)
"""
import os
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.mcp_client import get_mcp_tools
from services.base import ITicketService
from services.factory import get_ticket_service


_PRODUCT_KEYWORDS = {
    "retention": ["retention", "churn", "grr", "nrr"],
    "bookings":  ["bookings", "revenue", "arr", "mrr"],
    "cac":       ["cac", "marketing", "acquisition"],
    "ltv":       ["ltv", "lifetime"],
}


class CapacityAgent(BaseAgent):
    """
    Fetches Jira issues and creates tickets via ITicketService.
    In mock mode: MockJiraService (no credentials needed).
    In prod mode: JiraService (requires JIRA_* env vars).
    MCP tools (USE_MCP=true) are layered on top of the service when available.
    """
    name = "capacity_agent"
    description = "Fetches Jira issues and creates tickets"
    capabilities = [
        "issue_retrieval",
        "incident_tracking",
        "blocker_identification",
        "ticket_creation",
    ]

    def __init__(
        self,
        config=None,
        ticket_service: Optional[ITicketService] = None,
        **kwargs,
    ) -> None:
        """
        Args:
            config:         AppConfig (used by factory if ticket_service not provided)
            ticket_service: Explicit ITicketService injection (useful in tests)
        """
        kwargs.pop("enable_mock", None)
        super().__init__(config, enable_mock=False)
        self._svc: ITicketService = ticket_service or get_ticket_service(config)
        # MCP tools are optional — layered on top of the service if enabled
        self._mcp_tools = get_mcp_tools("jira")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        return [
            p for p, kws in _PRODUCT_KEYWORDS.items() if any(k in q for k in kws)
        ] or ["retention"]

    def _fetch_issues(self, product: str) -> List[Dict]:
        """Fetch via MCP if available, otherwise delegate to ITicketService."""
        if self._mcp_tools:
            return self._fetch_via_mcp(product)
        project_key = os.getenv("JIRA_PROJECT_KEY", "DATA")
        jql = (
            f'project = "{project_key}" AND labels = "{product}" '
            f"ORDER BY updated DESC"
        )
        raw = self._svc.search_issues(jql)
        return [
            {
                "id":       i["key"],
                "type":     (i["fields"].get("issuetype") or {}).get("name", "Issue"),
                "priority": (i["fields"].get("priority") or {}).get("name", "Medium"),
                "status":   (i["fields"].get("status") or {}).get("name", "Unknown"),
                "summary":  i["fields"].get("summary", ""),
                "assignee": (i["fields"].get("assignee") or {}).get(
                    "displayName",
                    (i["fields"].get("assignee") or {}).get("emailAddress", "Unassigned"),
                ),
                "labels":   i["fields"].get("labels", []),
            }
            for i in raw
        ]

    def _fetch_via_mcp(self, product: str) -> List[Dict]:
        try:
            tool = next(
                (t for t in self._mcp_tools if "search" in t.name.lower()), None
            )
            if not tool:
                return []
            raw = tool.run({"query": f"label:{product}"})
            return raw if isinstance(raw, list) else []
        except Exception as exc:
            self.logger.warning("Jira MCP fetch failed for %s: %s", product, exc)
            return []

    def _create_ticket_via_service(
        self,
        summary: str,
        description: str,
        issue_type: str,
        priority: str,
        labels: List[str],
    ) -> Dict:
        """Delegate to MCP create tool or ITicketService.create_issue."""
        if self._mcp_tools:
            tool = next(
                (t for t in self._mcp_tools if "create" in t.name.lower()), None
            )
            if tool:
                return tool.run(
                    {
                        "summary":     summary,
                        "description": description,
                        "issuetype":   issue_type,
                        "priority":    priority,
                        "labels":      labels,
                    }
                )
        return self._svc.create_issue(
            summary, description, issue_type, priority, labels
        )

    # ── IAgent ────────────────────────────────────────────────────────────

    def _execute(self, request: AgentRequest) -> AgentResult:
        is_write = any(
            kw in request.query.lower()
            for kw in [
                "create ticket", "open bug", "raise issue",
                "log incident", "create a bug", "file a ticket",
            ]
        )
        return self._handle_create(request) if is_write else self._handle_read(request)

    def _handle_read(self, request: AgentRequest) -> AgentResult:
        products   = request.data_products or self._resolve_products(request.query)
        all_issues: Dict[str, List] = {}
        sources:    List[str]       = []

        for product in products:
            all_issues[product] = self._fetch_issues(product)
            sources.append(f"Jira: {product.upper()}")

        open_count = sum(
            1
            for issues in all_issues.values()
            for i in issues
            if i.get("status") in ("Open", "In Progress")
        )
        return AgentResult(
            agent_name=self.name,
            success=True,
            data=all_issues,
            summary=self._build_read_summary(all_issues),
            sources=sources,
            confidence=0.90,
            metadata={"open_issues": open_count, "products": products},
        )

    def _handle_create(self, request: AgentRequest) -> AgentResult:
        ctx         = request.context or {}
        summary     = ctx.get("ticket_summary", f"Auto-detected issue: {request.query[:80]}")
        description = ctx.get("ticket_description", request.query)
        issue_type  = ctx.get("issue_type", "Bug")
        priority    = ctx.get("priority", "Medium")
        labels      = ctx.get("labels", ["auto-generated", "data-governance"])

        ticket    = self._create_ticket_via_service(summary, description, issue_type, priority, labels)
        ticket_id = ticket.get("key", "UNKNOWN")

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"✅ Jira {issue_type} created: **{ticket_id}**\n   {summary}",
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

    # ── Public convenience (called by auto_ticket_node) ───────────────────

    def create_ticket_from_anomaly(
        self,
        anomaly_description: str,
        product: str,
        priority: str = "High",
    ) -> AgentResult:
        """Called by graph/nodes.py auto_ticket_node after HITL approval."""
        return self.execute(
            AgentRequest(
                query=f"create ticket for {product} data quality issue",
                context={
                    "ticket_summary": (
                        f"[Auto-DQ] {product.upper()}: {anomaly_description[:100]}"
                    ),
                    "ticket_description": (
                        f"Automated data quality alert detected by "
                        f"Data Governance Copilot.\n\n"
                        f"Product: {product}\n"
                        f"Anomaly: {anomaly_description}\n\n"
                        f"Please investigate and resolve."
                    ),
                    "issue_type": "Bug",
                    "priority":   priority,
                    "labels":     ["auto-dq-alert", product, "data-governance"],
                },
                data_products=[product],
            )
        )

    # ── Summary formatting ────────────────────────────────────────────────

    def _build_read_summary(self, all_issues: Dict) -> str:
        parts      = ["🎫 **Jira Issues & Operational Status**"]
        total_open = 0
        for product, issues in all_issues.items():
            if not issues:
                parts.append(f"\n**{product.upper()}** — No open issues ✅")
                continue
            open_issues  = [i for i in issues if i.get("status") in ("Open", "In Progress")]
            total_open  += len(open_issues)
            parts.append(
                f"\n**{product.upper()}** — "
                f"{len(open_issues)} open / {len(issues)} total"
            )
            for issue in issues:
                picon = {"High": "🔴", "Critical": "🚨", "Medium": "🟡", "Low": "🟢"}.get(
                    issue.get("priority", ""), "⚪"
                )
                sicon = {"Done": "✅", "In Progress": "🔄", "Open": "🔴", "Known Issue": "📌"}.get(
                    issue.get("status", ""), "⚪"
                )
                parts.append(
                    f"  {picon} **{issue['id']}** [{issue.get('type','Issue')}] "
                    f"{sicon} {issue.get('status','')}\n"
                    f"     {issue['summary']}"
                )
        parts.append("\n✅ No open issues found." if total_open == 0 else f"\n_Total open: {total_open}_")
        return "\n".join(parts)