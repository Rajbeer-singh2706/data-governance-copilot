"""Service factory — single switching point for mock vs real."""
from __future__ import annotations

import os


def _use_mock() -> bool:
    return os.getenv("ENABLE_MOCK", "true").lower() == "true"


def get_data_service(config=None):
    from src.services.databricks.mock import MockDatabricksService
    if _use_mock():
        return MockDatabricksService()
    try:
        from src.services.databricks.real import DatabricksService
        return DatabricksService(config)
    except EnvironmentError:
        return MockDatabricksService()


def get_ticket_service(config=None):
    from src.services.jira.mock import MockJiraService
    if _use_mock():
        return MockJiraService()
    try:
        from src.services.jira.real import JiraService
        return JiraService()
    except EnvironmentError:
        return MockJiraService()


def get_metadata_service(config=None):
    from src.services.collibra.mock import MockCollibraService
    if _use_mock():
        return MockCollibraService()
    try:
        from src.services.collibra.real import CollibraService
        return CollibraService()
    except EnvironmentError:
        return MockCollibraService()


def get_vector_service(config=None):
    from src.services.pgvector.mock import NullVectorService
    if _use_mock():
        return NullVectorService()
    try:
        from src.services.pgvector.real import PGVectorService
        return PGVectorService(config)
    except EnvironmentError:
        return NullVectorService()
