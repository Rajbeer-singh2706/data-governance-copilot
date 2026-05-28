"""
src/services/jira/real.py
Real Jira REST API client.

Requires env vars:
  JIRA_BASE_URL, JIRA_API_TOKEN, JIRA_EMAIL

Raises EnvironmentError at construction if any are missing.
Satisfies ITicketService protocol.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from requests.auth import HTTPBasicAuth


class JiraService:
    """
    Thin wrapper around Jira REST API v3.
    Satisfies ITicketService protocol.
    """

    def __init__(self) -> None:
        self._base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        self._token    = os.getenv("JIRA_API_TOKEN", "")
        self._email    = os.getenv("JIRA_EMAIL", "")
        self._project  = os.getenv("JIRA_PROJECT_KEY", "DGC")

        if not all([self._base_url, self._token, self._email]):
            raise EnvironmentError(
                "JiraService requires JIRA_BASE_URL, JIRA_API_TOKEN, "
                "and JIRA_EMAIL to be set."
            )

        self._auth    = HTTPBasicAuth(self._email, self._token)
        self._headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # ── Internal ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: Dict = None) -> Any:
        resp = requests.get(
            f"{self._base_url}/rest/api/3{path}",
            auth=self._auth,
            headers=self._headers,
            params=params or {},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: Dict) -> Any:
        resp = requests.post(
            f"{self._base_url}/rest/api/3{path}",
            auth=self._auth,
            headers=self._headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ── ITicketService ─────────────────────────────────────────────────────

    def search_issues(self, jql: str, max_results: int = 20) -> List[Dict]:
        """Return list of issues matching JQL."""
        data = self._get("/search", params={"jql": jql, "maxResults": max_results})
        return data.get("issues", [])

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "High",
        labels: List[str] = None,
    ) -> Dict:
        """Create a Jira issue and return the response dict (includes 'key')."""
        payload = {
            "fields": {
                "project":   {"key": self._project},
                "summary":   summary,
                "issuetype": {"name": issue_type},
                "priority":  {"name": priority},
                "labels":    labels or [],
                "description": {
                    "type":    "doc",
                    "version": 1,
                    "content": [
                        {
                            "type":    "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
            }
        }
        return self._post("/issue", payload)