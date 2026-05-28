"""
src/services/base.py
Abstract protocols (interfaces) for every external service.

Each protocol defines ONLY the methods agents actually call.
Real and mock implementations both satisfy the same protocol —
agents never import a concrete class, only the protocol type.

Usage in agents:
    from services.base import IDataService, ITicketService, IMetadataService
    # agents receive a service via constructor injection
    def __init__(self, data_service: IDataService, ...):
        self._db = data_service
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


# ── Databricks / SQL ───────────────────────────────────────────────────────

@runtime_checkable
class IDataService(Protocol):
    """
    Structured data retrieval (Databricks SQL Warehouse or mock).
    Used by: InformationAgent
    """

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a SQL query and return rows as list-of-dicts."""
        ...


# ── Jira / Ticketing ───────────────────────────────────────────────────────

@runtime_checkable
class ITicketService(Protocol):
    """
    Issue tracker operations (Jira REST or mock).
    Used by: CapacityAgent
    """

    def search_issues(self, jql: str, max_results: int = 20) -> List[Dict]:
        """Return list of issues matching the JQL query."""
        ...

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str,
        priority: str,
        labels: List[str],
    ) -> Dict:
        """Create a new issue and return the created issue dict (must include 'key')."""
        ...


# ── Collibra / Metadata ────────────────────────────────────────────────────

@runtime_checkable
class IMetadataService(Protocol):
    """
    Governance metadata retrieval (Collibra DGC REST or mock).
    Used by: MetadataAgent
    """

    def search_assets(self, name: str) -> List[Dict]:
        """Search for data assets by name. Returns list of asset dicts."""
        ...

    def get_asset(self, asset_id: str) -> Dict:
        """Fetch a single asset by ID."""
        ...

    def get_data_quality(self, asset_id: str) -> Dict:
        """Return DQ metrics dict for an asset."""
        ...


# ── pgvector / Vector Store ────────────────────────────────────────────────
@runtime_checkable
class IVectorService(Protocol):
    """
    Semantic search / RAG (pgvector or mock).
    Used by: KnowledgeAgent
    """

    def similarity_search(
        self, query: str, k: int = 5
    ) -> List[Tuple[Any, float]]:
        """
        Return up to k (Document, score) tuples.
        score is 0.0–1.0 (higher = more relevant).
        """
        ...