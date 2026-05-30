"""Capacity Agent — delegates to ITicketService."""
from __future__ import annotations

from typing import List, Optional

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent
from src.core.mcp_client import get_mcp_tools


class CapacityAgent(BaseAgent):
    def __init__(self, config=None, ticket_service=None):
        from src.services.factory import get_ticket_service
        self._svc = ticket_service or get_ticket_service(config)
        self._mcp_tools = get_mcp_tools("jira")

    def execute(self, request: AgentRequest) -> AgentResult:
        try:
            jql = (
                f"project = DGC AND status != Done "
                f"ORDER BY priority DESC"
            )
            issues = self._svc.search_issues(jql, max_results=10)
            formatted = [
                {
                    "key": i.get("key", ""),
                    "summary": i.get("fields", {}).get("summary", ""),
                    "status": i.get("fields", {}).get("status", {}).get("name", ""),
                    "priority": i.get("fields", {}).get("priority", {}).get("name", ""),
                    "issue_type": i.get("fields", {}).get("issuetype", {}).get("name", ""),
                }
                for i in issues
            ]
            return AgentResult(
                success=True,
                data={"tickets": formatted, "total": len(formatted)},
                message=f"Found {len(formatted)} open tickets",
                confidence=0.90,
                sources=["jira://DGC"],
                metadata={"jql": jql},
            )
        except Exception as exc:
            return AgentResult.failure(f"CapacityAgent error: {exc}", str(exc))

    def create_ticket_from_anomaly(
        self,
        anomaly_description: str,
        product: str = "general",
        priority: str = "High",
    ) -> AgentResult:
        try:
            summary = f"[Auto] Data anomaly detected: {product}"
            description = (
                f"Automated ticket created by Data Governance Copilot.\n\n"
                f"Anomaly: {anomaly_description}\n"
                f"Product: {product}\n"
                f"Priority: {priority}"
            )
            ticket = self._svc.create_issue(
                summary=summary,
                description=description,
                issue_type="Bug",
                priority=priority,
                labels=["auto-generated", "data-governance", product],
            )
            return AgentResult(
                success=True,
                data={"ticket": ticket},
                message=f"Created ticket {ticket.get('key', 'unknown')}",
                confidence=0.95,
                sources=["jira://DGC"],
            )
        except Exception as exc:
            return AgentResult.failure(f"Failed to create ticket: {exc}", str(exc))
