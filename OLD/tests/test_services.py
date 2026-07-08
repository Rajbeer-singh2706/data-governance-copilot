"""
tests/test_services.py
Unit tests for the services layer.

Tests cover:
  1. Each mock service satisfies its protocol (duck-typing check)
  2. Mock services return expected shapes / fields
  3. Factory returns mock when ENABLE_MOCK=true (default in CI)
  4. Factory returns mock (graceful fallback) when real service env vars absent
  5. Agents accept injected services → no internal client construction
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch

# ── Protocols ──────────────────────────────────────────────────────────────

from services.base import IDataService, ITicketService, IMetadataService, IVectorService


# ── Mock service imports ───────────────────────────────────────────────────

from services.databricks.mock import MockDatabricksService
from services.jira.mock import MockJiraService
from services.collibra.mock import MockCollibraService
from services.pgvector.mock import NullVectorService


# ═══════════════════════════════════════════════════════════════════════════
# 1. Protocol conformance
# ═══════════════════════════════════════════════════════════════════════════

class TestProtocolConformance:
    def test_mock_databricks_satisfies_protocol(self):
        svc = MockDatabricksService()
        assert isinstance(svc, IDataService)

    def test_mock_jira_satisfies_protocol(self):
        svc = MockJiraService()
        assert isinstance(svc, ITicketService)

    def test_mock_collibra_satisfies_protocol(self):
        svc = MockCollibraService()
        assert isinstance(svc, IMetadataService)

    def test_null_vector_satisfies_protocol(self):
        svc = NullVectorService()
        assert isinstance(svc, IVectorService)


# ═══════════════════════════════════════════════════════════════════════════
# 2. MockDatabricksService
# ═══════════════════════════════════════════════════════════════════════════

class TestMockDatabricksService:
    def test_query_retention_returns_row(self):
        svc  = MockDatabricksService()
        rows = svc.query("SELECT * FROM analytics.retention_metrics WHERE period = 'last_month'")
        assert len(rows) == 1
        row = rows[0]
        assert "gross_retention_rate" in row
        assert "churn_rate" in row

    def test_query_bookings_returns_row(self):
        svc  = MockDatabricksService()
        rows = svc.query("SELECT * FROM analytics.bookings_fact WHERE period = 'last_month'")
        assert len(rows) == 1
        assert "total_bookings" in rows[0]

    def test_query_unknown_table_returns_default(self):
        svc  = MockDatabricksService()
        rows = svc.query("SELECT 1 FROM some_unknown_table")
        assert isinstance(rows, list)
        assert len(rows) >= 1

    def test_low_grr_scenario(self):
        svc  = MockDatabricksService(low_grr=True)
        rows = svc.query("SELECT * FROM analytics.retention_metrics")
        assert rows[0]["gross_retention_rate"] < 85


# ═══════════════════════════════════════════════════════════════════════════
# 3. MockJiraService
# ═══════════════════════════════════════════════════════════════════════════

class TestMockJiraService:
    def test_search_issues_returns_list(self):
        svc    = MockJiraService()
        issues = svc.search_issues('project = "DGC" ORDER BY updated DESC')
        assert isinstance(issues, list)
        assert len(issues) > 0

    def test_issue_has_required_fields(self):
        svc   = MockJiraService()
        issue = svc.search_issues("")[0]
        assert "key" in issue
        assert "fields" in issue
        assert "summary" in issue["fields"]
        assert "status" in issue["fields"]

    def test_create_issue_returns_key(self):
        svc    = MockJiraService()
        ticket = svc.create_issue(
            summary="Test ticket",
            description="Test description",
            issue_type="Bug",
            priority="High",
            labels=["test"],
        )
        assert "key" in ticket
        assert ticket["key"].startswith("DGC-")

    def test_created_tickets_are_stored(self):
        svc = MockJiraService()
        svc.create_issue("T1", "D1", "Bug", "High", [])
        svc.create_issue("T2", "D2", "Bug", "Medium", [])
        assert len(svc.tickets) == 2

    def test_keys_are_unique(self):
        svc = MockJiraService()
        t1  = svc.create_issue("A", "A", "Bug", "High", [])
        t2  = svc.create_issue("B", "B", "Bug", "High", [])
        assert t1["key"] != t2["key"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. MockCollibraService
# ═══════════════════════════════════════════════════════════════════════════

class TestMockCollibraService:
    def test_search_assets_returns_list(self):
        svc    = MockCollibraService()
        assets = svc.search_assets("retention")
        assert isinstance(assets, list)
        assert len(assets) > 0

    def test_search_asset_has_required_fields(self):
        svc   = MockCollibraService()
        asset = svc.search_assets("retention")[0]
        assert "id" in asset
        assert "name" in asset
        assert "owner" in asset

    def test_get_asset_by_id(self):
        svc   = MockCollibraService()
        asset = svc.get_asset("asset-001")
        assert asset["id"] == "asset-001"

    def test_get_asset_unknown_id(self):
        svc   = MockCollibraService()
        asset = svc.get_asset("nonexistent-id")
        assert "id" in asset  # still returns a dict

    def test_get_data_quality_returns_score(self):
        svc = MockCollibraService()
        dq  = svc.get_data_quality("asset-001")
        assert "score" in dq
        assert "passed" in dq
        assert "failed" in dq
        assert dq["passed"] + dq["failed"] == dq["total_rules"]

    def test_search_fallback_returns_all_assets(self):
        svc    = MockCollibraService()
        assets = svc.search_assets("zzznomatch")
        # fallback returns all assets
        assert len(assets) == 4


# ═══════════════════════════════════════════════════════════════════════════
# 5. NullVectorService
# ═══════════════════════════════════════════════════════════════════════════

class TestNullVectorService:
    def test_similarity_search_returns_tuples(self):
        svc     = NullVectorService()
        results = svc.similarity_search("retention churn grr", k=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_each_result_is_doc_score_tuple(self):
        from langchain_core.documents import Document
        svc     = NullVectorService()
        results = svc.similarity_search("data quality", k=3)
        for doc, score in results:
            assert isinstance(doc, Document)
            assert 0.0 <= score <= 1.0

    def test_keyword_relevance_boosts_score(self):
        svc = NullVectorService()
        # Query that matches retention doc keywords
        results_retention = svc.similarity_search("retention grr nrr churn", k=1)
        # Query with no keywords
        results_generic   = svc.similarity_search("something unrelated", k=1)
        # Top retention result should score >= generic top result
        assert results_retention[0][1] >= results_generic[0][1]

    def test_scores_above_threshold(self):
        svc     = NullVectorService()
        results = svc.similarity_search("governance policy", k=6)
        # All mock scores must pass the 0.70 filter in KnowledgeAgent
        assert all(score >= 0.70 for _, score in results)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Factory — mock mode (ENABLE_MOCK=true)
# ═══════════════════════════════════════════════════════════════════════════

class TestFactory:
    def test_get_data_service_returns_mock(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MOCK", "true")
        from services.factory import get_data_service
        svc = get_data_service()
        assert isinstance(svc, MockDatabricksService)

    def test_get_ticket_service_returns_mock(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MOCK", "true")
        from services.factory import get_ticket_service
        svc = get_ticket_service()
        assert isinstance(svc, MockJiraService)

    def test_get_metadata_service_returns_mock(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MOCK", "true")
        from services.factory import get_metadata_service
        svc = get_metadata_service()
        assert isinstance(svc, MockCollibraService)

    def test_get_vector_service_returns_null(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MOCK", "true")
        from services.factory import get_vector_service
        svc = get_vector_service()
        assert isinstance(svc, NullVectorService)

    def test_factory_falls_back_to_mock_when_real_missing_creds(self, monkeypatch):
        """Real services raise EnvironmentError → factory falls back to mock."""
        monkeypatch.setenv("ENABLE_MOCK", "false")
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.delenv("JIRA_EMAIL", raising=False)
        from services import factory
        # Force reimport to clear cached state
        import importlib; importlib.reload(factory)
        svc = factory.get_ticket_service()
        assert isinstance(svc, MockJiraService)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Agents accept injected services
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentServiceInjection:
    """Agents should work with any injected service — no internal construction."""

    def test_information_agent_uses_injected_service(self):
        from agents.information_agent import InformationAgent
        from core.base_agent import AgentRequest

        svc = MockDatabricksService()
        agent = InformationAgent(data_service=svc)
        result = agent.execute(AgentRequest(query="What is the retention rate?"))
        assert result.success
        assert "metrics" in result.data

    def test_capacity_agent_uses_injected_service(self):
        from agents.capacity_agent import CapacityAgent
        from core.base_agent import AgentRequest

        svc = MockJiraService()
        with patch("agents.capacity_agent.get_mcp_tools", return_value=[]):
            agent = CapacityAgent(ticket_service=svc)
        result = agent.execute(AgentRequest(query="Show open incidents for retention"))
        assert result.success

    def test_capacity_agent_create_ticket_uses_service(self):
        from agents.capacity_agent import CapacityAgent

        svc = MockJiraService()
        with patch("agents.capacity_agent.get_mcp_tools", return_value=[]):
            agent = CapacityAgent(ticket_service=svc)
        result = agent.create_ticket_from_anomaly(
            anomaly_description="GRR dropped to 78%",
            product="retention",
        )
        assert result.success
        assert len(svc.tickets) == 1
        assert svc.tickets[0]["key"].startswith("DGC-")

    def test_metadata_agent_uses_injected_service(self):
        from agents.metadata_agent import MetadataAgent
        from core.base_agent import AgentRequest

        svc = MockCollibraService()
        with patch("agents.metadata_agent.get_mcp_tools", return_value=[]):
            agent = MetadataAgent(metadata_service=svc)
        result = agent.execute(AgentRequest(query="What is the data quality for retention?"))
        assert result.success

    def test_knowledge_agent_uses_injected_service(self):
        from agents.knowledge_agent import KnowledgeAgent
        from core.base_agent import AgentRequest

        svc   = NullVectorService()
        agent = KnowledgeAgent(vector_service=svc)
        result = agent.execute(AgentRequest(query="What is the GRR policy?"))
        assert result.success
        assert "knowledge" in result.data