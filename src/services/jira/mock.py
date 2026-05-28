"""
src/services/jira/mock.py
Mock Jira service — in-memory ticket store for dev / CI.

No network calls, no credentials required.
Satisfies ITicketService protocol.

Tickets are stored in a list on the instance so tests can
inspect them after the agent runs:

    svc = MockJiraService()
    agent = CapacityAgent(ticket_service=svc)
    agent.execute(request)
    assert svc.tickets[0]["key"] == "DGC-1"
"""
from __future__ import annotations

from typing import Dict, List


# ── Canned open incidents (returned by search_issues) ─────────────────────

_OPEN_INCIDENTS: List[Dict] = [
    {
        "key": "DGC-101",
        "fields": {
            "summary":   "Retention metric pipeline delayed by 4 hours",
            "status":    {"name": "In Progress"},
            "priority":  {"name": "High"},
            "assignee":  {"displayName": "Alice Chen"},
            "created":   "2024-01-14T08:00:00.000+0000",
            "labels":    ["data-quality", "retention"],
        },
    },
    {
        "key": "DGC-102",
        "fields": {
            "summary":   "CAC metric missing marketing attribution data",
            "status":    {"name": "Open"},
            "priority":  {"name": "Medium"},
            "assignee":  {"displayName": "Bob Smith"},
            "created":   "2024-01-13T14:30:00.000+0000",
            "labels":    ["data-quality", "cac"],
        },
    },
    {
        "key": "DGC-103",
        "fields": {
            "summary":   "LTV calculation variance detected in enterprise segment",
            "status":    {"name": "Open"},
            "priority":  {"name": "High"},
            "assignee":  None,
            "created":   "2024-01-12T09:15:00.000+0000",
            "labels":    ["anomaly", "ltv"],
        },
    },
]


class MockJiraService:
    """
    In-memory Jira mock satisfying ITicketService.
    Supports inspecting created tickets after agent execution.
    """

    def __init__(self) -> None:
        self.tickets: List[Dict] = []   # tickets created during this session
        self._counter: int = 200        # auto-increment key counter

    # ── ITicketService ─────────────────────────────────────────────────────

    def search_issues(self, jql: str, max_results: int = 20) -> List[Dict]:
        """Return canned open incidents (ignores JQL content in mock)."""
        return _OPEN_INCIDENTS[:max_results]

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "High",
        labels: List[str] = None,
    ) -> Dict:
        """Create an in-memory ticket and return a dict with a 'key' field."""
        self._counter += 1
        ticket = {
            "key": f"DGC-{self._counter}",
            "fields": {
                "summary":    summary,
                "description": description,
                "issuetype":  {"name": issue_type},
                "priority":   {"name": priority},
                "labels":     labels or [],
                "status":     {"name": "Open"},
            },
        }
        self.tickets.append(ticket)
        return ticket