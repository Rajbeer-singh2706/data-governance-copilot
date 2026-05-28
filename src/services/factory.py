"""
src/services/factory.py
Service factory — the ONE place where ENABLE_MOCK is checked.

Agents call get_service() and receive a protocol-conforming object.
They never import a concrete class directly.

Usage:
    from services.factory import get_data_service, get_ticket_service
    from services.factory import get_metadata_service, get_vector_service

    class InformationAgent(BaseAgent):
        def __init__(self, config, data_service=None):
            self._db = data_service or get_data_service(config)

Switching:
    ENABLE_MOCK=true   → mock implementations (default in dev/CI)
    ENABLE_MOCK=false  → real implementations (require credentials)

If a real service raises EnvironmentError (missing credentials),
the factory logs a warning and returns the mock instead — so the
system always degrades gracefully rather than crashing at startup.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from services.base import IDataService, IMetadataService, ITicketService, IVectorService

logger = logging.getLogger(__name__)


def _is_mock() -> bool:
    return os.getenv("ENABLE_MOCK", "true").lower() == "true"


# ── Databricks ─────────────────────────────────────────────────────────────

def get_data_service(config=None) -> IDataService:
    """
    Returns MockDatabricksService (mock mode) or DatabricksService (prod).
    Falls back to mock if real service raises EnvironmentError.
    """
    if _is_mock():
        from services.databricks.mock import MockDatabricksService
        logger.debug("service.data → MockDatabricksService")
        return MockDatabricksService()

    try:
        from services.databricks.real import DatabricksService
        svc = DatabricksService(config.databricks if config else None)
        logger.info("service.data → DatabricksService (real)")
        return svc
    except EnvironmentError as e:
        logger.warning("DatabricksService unavailable (%s) — using mock", e)
        from services.databricks.mock import MockDatabricksService
        return MockDatabricksService()


# ── Jira ───────────────────────────────────────────────────────────────────

def get_ticket_service(config=None) -> ITicketService:
    """
    Returns MockJiraService (mock mode) or JiraService (prod).
    Falls back to mock if real service raises EnvironmentError.
    """
    if _is_mock():
        from services.jira.mock import MockJiraService
        logger.debug("service.ticket → MockJiraService")
        return MockJiraService()

    try:
        from services.jira.real import JiraService
        svc = JiraService()
        logger.info("service.ticket → JiraService (real)")
        return svc
    except EnvironmentError as e:
        logger.warning("JiraService unavailable (%s) — using mock", e)
        from services.jira.mock import MockJiraService
        return MockJiraService()


# ── Collibra ───────────────────────────────────────────────────────────────

def get_metadata_service(config=None) -> IMetadataService:
    """
    Returns MockCollibraService (mock mode) or CollibraService (prod).
    Falls back to mock if real service raises EnvironmentError.
    """
    if _is_mock():
        from services.collibra.mock import MockCollibraService
        logger.debug("service.metadata → MockCollibraService")
        return MockCollibraService()

    try:
        from services.collibra.real import CollibraService
        svc = CollibraService()
        logger.info("service.metadata → CollibraService (real)")
        return svc
    except EnvironmentError as e:
        logger.warning("CollibraService unavailable (%s) — using mock", e)
        from services.collibra.mock import MockCollibraService
        return MockCollibraService()


# ── pgvector ───────────────────────────────────────────────────────────────

def get_vector_service(config=None) -> IVectorService:
    """
    Returns NullVectorService (mock mode) or PGVectorService (prod).
    Falls back to NullVectorService if real service raises EnvironmentError.
    """
    if _is_mock():
        from services.pgvector.mock import NullVectorService
        logger.debug("service.vector → NullVectorService")
        return NullVectorService()

    try:
        from services.pgvector.real import PGVectorService
        svc = PGVectorService(config.vector_db if config else None)
        logger.info("service.vector → PGVectorService (real)")
        return svc
    except EnvironmentError as e:
        logger.warning("PGVectorService unavailable (%s) — using mock", e)
        from services.pgvector.mock import NullVectorService
        return NullVectorService()