"""Mock Jira service — in-memory store, inspectable .tickets list."""
from __future__ import annotations

from typing import Dict, List

_CANNED_ISSUES = [
    {"key": "DGC-101", "fields": {"summary": "Retention GRR below threshold",
     "status": {"name": "Open"}, "priority": {"name": "High"},
     "issuetype": {"name": "Bug"}, "assignee": None}},
    {"key": "DGC-102", "fields": {"summary": "CAC data quality failure",
     "status": {"name": "In Progress"}, "priority": {"name": "Medium"},
     "issuetype": {"name": "Bug"}, "assignee": None}},
    {"key": "DGC-103", "fields": {"summary": "LTV model drift detected",
     "status": {"name": "Open"}, "priority": {"name": "High"},
     "issuetype": {"name": "Task"}, "assignee": None}},
]

_counter = 200


class MockJiraService:
    def __init__(self):
        self.tickets: List[Dict] = []

    def search_issues(self, jql: str, max_results: int = 10) -> List[Dict]:
        return _CANNED_ISSUES[:max_results]

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "Medium",
        labels: List[str] = None,
    ) -> Dict:
        global _counter
        _counter += 1
        ticket = {
            "key": f"DGC-{_counter}",
            "fields": {
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "labels": labels or [],
                "status": {"name": "Open"},
            },
        }
        self.tickets.append(ticket)
        return ticket
