"""
Day 20 — Production readiness tests.
Validates: health endpoints, config hardening, error handling, protocol conformance.
"""
from __future__ import annotations

import os
import pytest

os.environ["ENABLE_MOCK"] = "true"
os.environ["REDIS_ENABLED"] = "false"


# ── Protocol Conformance ───────────────────────────────────────────────────────

class TestProtocolConformance:
    """All services must satisfy their runtime-checkable Protocol."""

    def test_mock_databricks_conforms(self):
        from src.services.base import IDataService
        from src.services.databricks.mock import MockDatabricksService
        assert isinstance(MockDatabricksService(), IDataService)

    def test_mock_jira_conforms(self):
        from src.services.base import ITicketService
        from src.services.jira.mock import MockJiraService
        assert isinstance(MockJiraService(), ITicketService)

    def test_mock_collibra_conforms(self):
        from src.services.base import IMetadataService
        from src.services.collibra.mock import MockCollibraService
        assert isinstance(MockCollibraService(), IMetadataService)

    def test_null_vector_conforms(self):
        from src.services.base import IVectorService
        from src.services.pgvector.mock import NullVectorService
        assert isinstance(NullVectorService(), IVectorService)


# ── FastAPI Health Endpoints ───────────────────────────────────────────────────

class TestFastAPIHealth:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_health_endpoint_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data

    def test_agents_status_endpoint(self, client):
        resp = client.get("/agents/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert len(data["agents"]) == 5
        assert "mock_mode" in data
        assert "token_usage" in data

    def test_teams_health_endpoint(self, client):
        resp = client.get("/teams/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_query_endpoint_returns_summary(self, client):
        from unittest.mock import patch
        mock_result = {
            "final_summary": "Retention rate is healthy at 92.5%.",
            "confidence": 0.95, "anomalies": [], "sources": ["analytics.retention"],
            "execution_ms": 120.0, "query_id": "abc123", "pending_action": None,
        }
        with patch("src.api.app._run_graph", return_value=mock_result):
            resp = client.post("/query", json={
                "query": "What is our retention rate?",
                "thread_id": "prod-test",
                "data_products": ["retention"],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "confidence" in data
        assert "execution_ms" in data

    def test_query_endpoint_short_query_handled(self, client):
        """Short query blocked by guardrails — should return cleanly, not 500."""
        resp = client.post("/query", json={"query": "hi", "thread_id": "test"})
        # Either 200 with empty summary (guardrail blocked) or handled error
        assert resp.status_code in (200, 400, 422)

    def test_history_endpoint(self, client):
        resp = client.get("/history/test-thread-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "test-thread-001"

    def test_query_stream_endpoint(self, client):
        from unittest.mock import patch
        mock_result = {
            "final_summary": "CAC is 2850, within acceptable range.",
            "confidence": 0.9, "anomalies": [],
        }
        with patch("src.api.app._run_graph", return_value=mock_result):
            resp = client.post("/query/stream", json={
                "query": "Analyze our CAC metrics",
                "thread_id": "stream-test",
                "data_products": ["cac"],
            })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        text = resp.text
        assert "event" in text


# ── Error Handling ─────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_agent_result_failure_factory(self):
        from src.core.base_agent import AgentResult
        r = AgentResult.failure("something went wrong", "KeyError: 'grr'")
        assert r.success is False
        assert r.confidence == 0.0
        assert "KeyError" in r.errors[0]
        assert r.message == "something went wrong"

    def test_information_agent_handles_service_error(self):
        from src.agents.information_agent import InformationAgent
        from src.core.base_agent import AgentRequest

        class BrokenService:
            def query(self, sql):
                raise RuntimeError("DB connection refused")

        agent = InformationAgent(data_service=BrokenService())
        req = AgentRequest(query="retention check", data_products=["retention"])
        result = agent.execute(req)
        assert result.success is False
        assert len(result.errors) > 0

    def test_knowledge_agent_handles_service_error(self):
        from src.agents.knowledge_agent import KnowledgeAgent
        from src.core.base_agent import AgentRequest

        class BrokenVectorService:
            def similarity_search(self, query, k=5):
                raise ConnectionError("pgvector unavailable")

        agent = KnowledgeAgent(vector_service=BrokenVectorService())
        req = AgentRequest(query="governance policy")
        result = agent.execute(req)
        assert result.success is False

    def test_metadata_agent_handles_service_error(self):
        from src.agents.metadata_agent import MetadataAgent
        from src.core.base_agent import AgentRequest

        class BrokenMetaService:
            def search_assets(self, name):
                raise TimeoutError("Collibra timeout")
            def get_asset(self, aid): pass
            def get_data_quality(self, aid): pass

        agent = MetadataAgent(metadata_service=BrokenMetaService())
        req = AgentRequest(query="retention metadata")
        result = agent.execute(req)
        assert result.success is False

    def test_capacity_agent_handles_service_error(self):
        from src.agents.capacity_agent import CapacityAgent
        from src.core.base_agent import AgentRequest

        class BrokenJira:
            def search_issues(self, jql, max_results=10):
                raise RuntimeError("Jira down")
            def create_issue(self, *a, **kw): pass

        agent = CapacityAgent(ticket_service=BrokenJira())
        req = AgentRequest(query="show tickets")
        result = agent.execute(req)
        assert result.success is False

    def test_retry_exhaustion_returns_agent_result(self):
        from src.core.base_agent import AgentRequest, AgentResult
        from src.core.retry import retry_agent_call

        attempts = []
        def flaky(req):
            attempts.append(1)
            raise RuntimeError("always fails")

        result = retry_agent_call(flaky, AgentRequest(query="test"), max_retries=1)
        assert result.success is False
        assert len(attempts) == 2  # 1 initial + 1 retry


# ── Logging Utils ──────────────────────────────────────────────────────────────

class TestLoggingUtils:
    def test_get_logger_returns_logger(self):
        from src.core.logging_utils import get_logger
        logger = get_logger("test.module")
        assert logger is not None
        assert logger.name == "test.module"

    def test_log_execution_decorator_passes_result(self):
        from src.core.logging_utils import get_logger, log_execution
        logger = get_logger("test")

        @log_execution(logger)
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_log_execution_propagates_exception(self):
        from src.core.logging_utils import get_logger, log_execution
        logger = get_logger("test")

        @log_execution(logger)
        def boom():
            raise ValueError("intentional")

        with pytest.raises(ValueError):
            boom()

    def test_error_hierarchy(self):
        from src.core.logging_utils import GovernanceError, AgentError, ServiceError, ConfigurationError
        assert issubclass(AgentError, GovernanceError)
        assert issubclass(ServiceError, GovernanceError)
        assert issubclass(ConfigurationError, GovernanceError)


# ── Teams Cards ────────────────────────────────────────────────────────────────

class TestTeamsCards:
    def test_build_response_card_structure(self):
        from src.teams.cards import build_response_card
        result = {"final_summary": "Retention is healthy.", "anomalies": [], "confidence": 0.95}
        card = build_response_card(result)
        assert card["type"] == "AdaptiveCard"
        assert len(card["body"]) >= 2

    def test_build_response_card_with_anomalies(self):
        from src.teams.cards import build_response_card
        result = {
            "final_summary": "Issues detected.",
            "anomalies": ["GRR below threshold", "CAC payback exceeded"],
            "confidence": 0.7,
        }
        card = build_response_card(result)
        body_text = str(card)
        assert "Anomalies" in body_text

    def test_build_hitl_card_has_approve_reject(self):
        from src.teams.cards import build_hitl_card
        card = build_hitl_card(
            {"description": "Create 2 tickets?", "anomalies": []},
            thread_id="t1", query="check retention",
        )
        actions = card.get("actions", [])
        titles = [a["title"] for a in actions]
        assert any("Approve" in t for t in titles)
        assert any("Reject" in t for t in titles)

    def test_build_error_card(self):
        from src.teams.cards import build_error_card
        card = build_error_card("Something went wrong")
        assert card["type"] == "AdaptiveCard"
        assert any("Error" in str(b) for b in card["body"])

    def test_build_welcome_card(self):
        from src.teams.cards import build_welcome_card
        card = build_welcome_card()
        assert card["type"] == "AdaptiveCard"

    def test_build_thinking_card(self):
        from src.teams.cards import build_thinking_card
        card = build_thinking_card()
        assert card["type"] == "AdaptiveCard"


# ── Teams Models ───────────────────────────────────────────────────────────────

class TestTeamsModels:
    def test_teams_activity_parses_message(self):
        from src.teams.models import TeamsActivity
        payload = {
            "type": "message",
            "id": "msg-001",
            "text": "What is our retention rate?",
            "from": {"id": "user-1", "name": "Alice"},
            "conversation": {"id": "conv-1"},
        }
        activity = TeamsActivity.model_validate(payload)
        assert activity.type == "message"
        assert activity.text == "What is our retention rate?"
        assert activity.from_user.name == "Alice"

    def test_teams_activity_parses_invoke(self):
        from src.teams.models import TeamsActivity
        payload = {
            "type": "invoke",
            "id": "inv-001",
            "value": {"action": "approve", "thread_id": "t1"},
        }
        activity = TeamsActivity.model_validate(payload)
        assert activity.type == "invoke"
        assert activity.value["action"] == "approve"

    def test_teams_user_defaults(self):
        from src.teams.models import TeamsUser
        user = TeamsUser()
        assert user.id == ""
        assert user.name == ""


# ── Ingestion Pipeline ─────────────────────────────────────────────────────────

class TestIngestionCoverage:
    def test_loader_raises_for_unknown_extension(self):
        from src.ingestion.loaders import load_document
        with pytest.raises(ValueError, match="Unsupported"):
            load_document("mystery.xyz")

    def test_chunker_adds_content_hash(self):
        from src.ingestion.chunker import chunk_documents
        from langchain_core.documents import Document
        docs = [Document(page_content="Retention metrics governance policy.", metadata={"source": "retention_policy.pdf"})]
        chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=64)
        assert all("content_hash" in c.metadata for c in chunks)

    def test_chunker_infers_retention_product(self):
        from src.ingestion.chunker import chunk_documents
        from langchain_core.documents import Document
        docs = [Document(page_content="GRR and NRR metrics.", metadata={"source": "retention_report.pdf"})]
        chunks = chunk_documents(docs)
        assert chunks[0].metadata["product"] == "retention"

    def test_chunker_infers_bookings_product(self):
        from src.ingestion.chunker import chunk_documents
        from langchain_core.documents import Document
        docs = [Document(page_content="ARR analysis.", metadata={"source": "bookings_q4.pdf"})]
        chunks = chunk_documents(docs)
        assert chunks[0].metadata["product"] == "bookings"

    def test_chunker_general_for_unknown_source(self):
        from src.ingestion.chunker import chunk_documents
        from langchain_core.documents import Document
        docs = [Document(page_content="Some content.", metadata={"source": "unknown_doc.pdf"})]
        chunks = chunk_documents(docs)
        assert chunks[0].metadata["product"] == "general"

    def test_chunker_empty_returns_empty(self):
        from src.ingestion.chunker import chunk_documents
        assert chunk_documents([]) == []

    def test_embedder_returns_parallel_vectors(self):
        from src.ingestion.embedder import embed_chunks
        from langchain_core.documents import Document
        from unittest.mock import patch, MagicMock

        chunks = [Document(page_content="text one", metadata={}),
                  Document(page_content="text two", metadata={})]
        fake_vecs = [[0.1] * 1536, [0.2] * 1536]
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = fake_vecs

        with patch("src.ingestion.embedder.OpenAIEmbeddings", return_value=mock_emb):
            result = embed_chunks(chunks)

        assert len(result) == 2
        assert len(result[0]) == 1536

    def test_store_skips_all_duplicates(self):
        import hashlib
        import src.ingestion.store as store_module
        from src.ingestion.store import upsert_chunks
        from langchain_core.documents import Document
        from unittest.mock import patch, MagicMock

        chunk = Document(page_content="existing content", metadata={
            "content_hash": hashlib.sha256(b"existing content").hexdigest()
        })
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(chunk.metadata["content_hash"],)]
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(store_module.psycopg2, "connect", return_value=mock_conn), \
             patch("src.ingestion.store.PGVector"), \
             patch("src.ingestion.store.OpenAIEmbeddings"):
            result = upsert_chunks([chunk], [[0.1] * 1536])

        assert result == 0

    def test_store_inserts_new_chunks(self):
        import hashlib
        from src.ingestion.store import upsert_chunks
        from langchain_core.documents import Document
        from unittest.mock import patch, MagicMock

        chunk = Document(page_content="brand new content", metadata={
            "content_hash": hashlib.sha256(b"brand new content").hexdigest(),
            "source": "new.pdf", "product": "retention",
        })

        with patch("psycopg2.connect") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_pg.connect.return_value = mock_conn

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            result = upsert_chunks([chunk], [[0.1] * 1536])

        assert result == 1
        mock_store.add_embeddings.assert_called_once()


# ── State TypedDict ────────────────────────────────────────────────────────────

class TestStateCoverage:
    def test_agent_state_can_be_instantiated(self):
        from src.graph.state import AgentState
        state: AgentState = {
            "query": "test",
            "thread_id": "t1",
            "user_id": "u1",
            "time_range": "last_30_days",
            "data_products": [],
            "intent": "metric_analysis",
            "next_agents": ["information"],
            "agent_results": [],
            "sources": [],
            "anomalies": [],
            "errors": [],
            "auto_tickets": [],
            "pending_action": None,
            "approved": False,
            "final_summary": "",
            "confidence": 0.0,
            "conversation_history": [],
            "user_preferences": {},
            "execution_ms": 0.0,
            "query_id": "abc123",
            "start_time": 0.0,
            "guardrail_passed": True,
        }
        assert state["query"] == "test"
        assert state["guardrail_passed"] is True
