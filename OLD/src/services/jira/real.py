"""Real Jira REST v3 service."""
from __future__ import annotations

import os
from typing import Dict, List

import requests


class JiraService:
    def __init__(self):
        self.base_url = os.getenv("JIRA_BASE_URL", "")
        self.token = os.getenv("JIRA_API_TOKEN", "")
        self.email = os.getenv("JIRA_EMAIL", "")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "DGC")
        if not all([self.base_url, self.token, self.email]):
            raise EnvironmentError("JIRA_BASE_URL, JIRA_API_TOKEN, JIRA_EMAIL are required")
        self._auth = (self.email, self.token)
        self._headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def search_issues(self, jql: str, max_results: int = 10) -> List[Dict]:
        resp = requests.post(
            f"{self.base_url}/rest/api/3/issue/search",
            json={"jql": jql, "maxResults": max_results},
            auth=self._auth, headers=self._headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def create_issue(self, summary: str, description: str,
                     issue_type: str = "Bug", priority: str = "Medium",
                     labels: List[str] = None) -> Dict:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {"type": "doc", "version": 1,
                                 "content": [{"type": "paragraph",
                                              "content": [{"type": "text", "text": description}]}]},
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "labels": labels or [],
            }
        }
        resp = requests.post(
            f"{self.base_url}/rest/api/3/issue",
            json=payload, auth=self._auth, headers=self._headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
