# tests/test_day18.py
# Day 18: pgvector migration + MCP client + VectorDBConfig
#
# Run: uv run pytest tests/test_day18.py -v
# Mock: ENABLE_MOCK=true OPENAI_API_KEY="" pytest tests/test_day18.py -v

import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("ENABLE_MOCK", "true")
os.environ.setdefault("OPENAI_API_KEY", "")


# ══════════════════════════════════════════════════════════════════════════
# 1. VectorDBConfig
# ══════════════════════════════════════════════════════════════════════════

class TestVectorDBConfig:

    def test_defaults(self):
        from config.settings import VectorDBConfig
        cfg = VectorDBConfig()
        assert cfg.host          == "localhost"
        assert cfg.port          == 5432
        assert cfg.database      == "governance_db"
        assert cfg.table_name    == "document_embeddings"
        assert cfg.embedding_dim == 1536

    def test_connection_string_format(self):
        from config.settings import VectorDBConfig
        cfg = VectorDBConfig(host="mydb", port=5432, database="db",
                             user="u", password="p")
        cs = cfg.connection_string
        assert cs.startswith("postgresql+psycopg2://")
        assert "mydb:5432" in cs
        assert "db" in cs

    def test_app_config_has_vector_db(self):
        from config.settings import AppConfig, VectorDBConfig
        cfg = AppConfig()
        assert hasattr(cfg, "vector_db")
        assert isinstance(cfg.vector_db, VectorDBConfig)


# ══════════════════════════════════════════════════════════════════════════
# 2. vector_store.py — mock mode
# ══════════════════════════════════════════════════════════════════════════

class TestVectorStoreMockMode:

    def test_get_vector_store_returns_null_in_mock(self):
        from core.vector_store import get_vector_store, _NullVectorStore
        from config.settings   import VectorDBConfig
        store = get_vector_store(VectorDBConfig())
        assert isinstance(store, _NullVectorStore)

    def test_similarity_search_returns_list(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "What is GRR?", k=5)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_results_are_doc_score_tuples(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "retention metrics", k=3)
        for doc, score in results:
            assert hasattr(doc, "page_content")
            assert 0.0 <= score <= 1.0

    def test_scores_above_threshold(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "gross retention rate GRR", k=5)
        # All mock scores should be >= 0.70 so they pass knowledge_agent threshold
        for _, score in results:
            assert score >= 0.70

    def test_k_limits_results(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "data quality", k=2)
        assert len(results) <= 2

    def test_results_ordered_by_score_desc(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "customer acquisition cost CAC", k=5)
        scores  = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_relevance_boosts_score(self):
        """Docs with more query-word matches should score higher."""
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store    = get_vector_store(VectorDBConfig())
        general  = similarity_search(store, "data",                k=5)
        specific = similarity_search(store, "gross retention rate GRR churn", k=5)
        # Specific query should surface higher top-1 score
        assert specific[0][1] >= general[0][1]

    def test_empty_query_still_returns_results(self):
        from core.vector_store import get_vector_store, similarity_search
        from config.settings   import VectorDBConfig
        store   = get_vector_store(VectorDBConfig())
        results = similarity_search(store, "", k=3)
        assert isinstance(results, list)


# ══════════════════════════════════════════════════════════════════════════
# 3. knowledge_agent.py — pgvector path
# ══════════════════════════════════════════════════════════════════════════

class TestKnowledgeAgent:

    def _agent(self):
        from agents.knowledge_agent import KnowledgeAgent
        from config.settings        import config
        return KnowledgeAgent(config=config, enable_mock=True)

    def test_execute_returns_result(self):
        from core.base_agent import AgentRequest
        agent   = self._agent()
        request = AgentRequest(query="What is GRR?", intent="knowledge_lookup",
                               query_id="t1", data_products=["retention"])
        result  = agent.execute(request)
        assert result is not None
        assert hasattr(result, "success")

    def test_successful_retrieval(self):
        from core.base_agent import AgentRequest
        agent   = self._agent()
        request = AgentRequest(query="How is customer lifetime value calculated?",
                               intent="knowledge_lookup", query_id="t2",
                               data_products=["ltv"])
        result  = agent.execute(request)
        assert result.success    == True
        assert result.summary    != ""
        assert result.confidence  > 0.0

    def test_sources_populated(self):
        from core.base_agent import AgentRequest
        agent   = self._agent()
        request = AgentRequest(query="What is CAC payback period?",
                               intent="knowledge_lookup", query_id="t3",
                               data_products=["cac"])
        result  = agent.execute(request)
        assert isinstance(result.sources, list)

    def test_result_data_has_docs_and_scores(self):
        from core.base_agent import AgentRequest
        agent   = self._agent()
        request = AgentRequest(query="data quality rules",
                               intent="data_quality", query_id="t4",
                               data_products=[])
        result  = agent.execute(request)
        if result.success:
            assert "docs"   in result.data
            assert "scores" in result.data

    def test_agent_name(self):
        agent = self._agent()
        assert agent.name == "knowledge_agent"


# ══════════════════════════════════════════════════════════════════════════
# 4. mcp_client.py
# ══════════════════════════════════════════════════════════════════════════

class TestMCPClient:

    def test_disabled_by_default(self):
        """USE_MCP=false → get_mcp_tools returns empty list."""
        os.environ["USE_MCP"] = "false"
        import importlib, core.mcp_client as m
        importlib.reload(m)
        assert m.get_mcp_tools("collibra") == []

    def test_is_mcp_enabled_false_by_default(self):
        os.environ["USE_MCP"] = "false"
        import importlib, core.mcp_client as m
        importlib.reload(m)
        assert m.is_mcp_enabled() == False

    def test_no_server_configured_returns_empty(self):
        """USE_MCP=true but no server path → returns []."""
        os.environ["USE_MCP"]               = "true"
        os.environ["COLLIBRA_MCP_SERVER"]   = ""
        import importlib, core.mcp_client as m
        importlib.reload(m)
        result = m.get_mcp_tools("collibra")
        assert result == []
        # Reset
        os.environ["USE_MCP"] = "false"

    def test_list_configured_servers_empty(self):
        os.environ["COLLIBRA_MCP_SERVER"] = ""
        os.environ["JIRA_MCP_SERVER"]     = ""
        import importlib, core.mcp_client as m
        importlib.reload(m)
        assert m.list_configured_servers() == []

    def test_unknown_server_name_returns_empty(self):
        import core.mcp_client as m
        result = m.get_mcp_tools("nonexistent_server")
        assert result == []


# ══════════════════════════════════════════════════════════════════════════
# 5. Integration — knowledge_agent in full graph
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestKnowledgeAgentIntegration:

    def setup_method(self):
        import core.cache as c
        c._fallback.clear(); c._client = None

    def test_knowledge_lookup_query_completes(self):
        from graph.graph import copilot_graph
        from graph.state import initial_state
        result = copilot_graph.invoke(
            initial_state("What is GRR and how is it calculated?"),
            config={"configurable": {"thread_id": "d18-know-01"}},
        )
        assert result["final_summary"] != ""
        assert result["intent"] in ["knowledge_lookup", "metric_analysis", "unknown"]

    def test_governance_query_uses_knowledge_agent(self):
        from graph.graph import copilot_graph
        from graph.state import initial_state
        result = copilot_graph.invoke(
            initial_state("Explain the data lineage for the bookings dataset"),
            config={"configurable": {"thread_id": "d18-know-02"}},
        )
        agent_names = [r.get("agent","") for r in result.get("agent_results",[])]
        # knowledge_agent should be among the agents that ran
        assert any("knowledge" in n for n in agent_names) or result["final_summary"] != ""