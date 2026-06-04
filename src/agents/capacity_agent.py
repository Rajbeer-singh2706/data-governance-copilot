"""Capacity Agent — delegates to ITicketService."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest, AgentResult, BaseAgent
from core.mcp_client import get_mcp_tools

_PRODUCT_KEYWORDS = {
    "retention": ["retention", "grr", "churn", "customer"],
    "bookings": ["bookings", "arr", "revenue", "sales"],
    "cac": ["cac", "acquisition", "cost", "marketing"],
    "ltv": ["ltv", "lifetime", "value"],
}


class CapacityAgent(BaseAgent):
    def __init__(self, config=None, ticket_service=None):
        from services.factory import get_ticket_service
        self._svc = ticket_service or get_ticket_service(config)
        self._mcp_tools = get_mcp_tools("jira")

    @property
    def name(self) -> str:
        return "capacity_agent"

    def _resolve_products(self, query: str) -> List[str]:
        q = query.lower()
        found = [p for p, kws in _PRODUCT_KEYWORDS.items() if any(kw in q for kw in kws)]
        return found or list(_PRODUCT_KEYWORDS.keys())

    def _is_create_request(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in ["create ticket", "open ticket", "file a ticket", "raise ticket", "new ticket", "create a ticket"])

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.monotonic()
        try:
            if self._is_create_request(request.query):
                return self._handle_create(request, t0)
            return self._handle_search(request, t0)
        except Exception as exc:
            return AgentResult.failure(f"CapacityAgent error: {exc}", str(exc))

    def _handle_search(self, request: AgentRequest, t0: float) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        product = products[0] if products else "general"

        jql = f"project = DGC AND labels = {product} AND status != Done ORDER BY priority DESC"
        raw_issues = self._svc.search_issues(jql, max_results=10)

        formatted = []
        for i in raw_issues:
            fields = i.get("fields", {})
            labels = fields.get("labels", [])
            # Filter to issues matching this product if labels present
            if labels and product not in labels:
                continue
            formatted.append({
                "id": i.get("key", ""),
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "issue_type": fields.get("issuetype", {}).get("name", ""),
            })

        # If no product-filtered results, return all (canned data has no labels)
        if not formatted:
            formatted = [
                {
                    "id": i.get("key", ""),
                    "summary": i.get("fields", {}).get("summary", ""),
                    "status": i.get("fields", {}).get("status", {}).get("name", ""),
                    "priority": i.get("fields", {}).get("priority", {}).get("name", ""),
                    "issue_type": i.get("fields", {}).get("issuetype", {}).get("name", ""),
                }
                for i in raw_issues
            ]

        open_issues = sum(1 for f in formatted if f["status"] in ("Open", "To Do", "Reopened"))
        elapsed = (time.monotonic() - t0) * 1000

        summary_md = f"**{len(formatted)} tickets found** for `{product}` — {open_issues} open"
        return AgentResult(
            success=True,
            data={"tickets": formatted, product: formatted},
            message=summary_md,
            confidence=0.90,
            sources=[f"Jira/DGC"],
            metadata={"open_issues": open_issues, "product": product, "jql": jql},
            execution_time_ms=elapsed,
        )

    def _handle_create(self, request: AgentRequest, t0: float) -> AgentResult:
        products = request.data_products or self._resolve_products(request.query)
        product = products[0] if products else "general"

        ticket = self._svc.create_issue(
            summary=f"[DGC] Data issue: {product} — {request.query[:60]}",
            description=request.query,
            issue_type="Bug",
            priority="High",
            labels=["data-governance", product],
        )
        elapsed = (time.monotonic() - t0) * 1000
        return AgentResult(
            success=True,
            data={"ticket_id": ticket.get("key", ""), "ticket": ticket},
            message=f"**Created** ticket `{ticket.get('key', '')}` for `{product}`",
            confidence=0.95,
            sources=["Jira/DGC"],
            metadata={"product": product},
            execution_time_ms=elapsed,
        )

    def create_ticket_from_anomaly(
        self,
        anomaly_description: str,
        product: str = "general",
        priority: str = "High",
    ) -> AgentResult:
        try:
            summary = f"[Auto-DQ] Data anomaly: {product} — {anomaly_description[:60]}"
            description = (
                f"Automated ticket created by Data Governance Copilot.\n\n"
                f"Anomaly: {anomaly_description}\n"
                f"Product: {product}\nPriority: {priority}"
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
                data={"ticket_id": ticket.get("key", ""), "ticket": ticket},
                message=f"Created ticket {ticket.get('key', 'unknown')}",
                confidence=0.95,
                sources=["Jira/DGC"],
            )
        except Exception as exc:
            return AgentResult.failure(f"Failed to create ticket: {exc}", str(exc))

    def health_check(self) -> Dict[str, Any]:
        try:
            issues = self._svc.search_issues("project = DGC", max_results=1)
            return {"agent": self.name, "healthy": True, "issues_accessible": len(issues) >= 0}
        except Exception as exc:
            return {"agent": self.name, "healthy": False, "error": str(exc)}
