"""Shared pytest fixtures and sys.path configuration."""
from __future__ import annotations

import os
import sys

# Ensure src/ is on path so both 'from agents.x' and 'from src.agents.x' work
_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Set default env vars for testing
os.environ.setdefault("ENABLE_MOCK", "true")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_data_service():
    from services.databricks.mock import MockDatabricksService
    return MockDatabricksService()


@pytest.fixture
def mock_ticket_service():
    from services.jira.mock import MockJiraService
    return MockJiraService()


@pytest.fixture
def mock_metadata_service():
    from services.collibra.mock import MockCollibraService
    return MockCollibraService()


@pytest.fixture
def mock_vector_service():
    from services.pgvector.mock import NullVectorService
    return NullVectorService()


@pytest.fixture
def sample_request():
    from core.base_agent import AgentRequest
    return AgentRequest(
        query="What is the current GRR for retention?",
        data_products=["retention"],
        thread_id="test-thread",
        user_id="test-user",
    )
