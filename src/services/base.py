"""Abstract service protocols."""
from __future__ import annotations

from typing import Dict, List, Protocol, Tuple, runtime_checkable

from langchain_core.documents import Document


@runtime_checkable
class IDataService(Protocol):
    def query(self, sql: str) -> List[Dict]: ...


@runtime_checkable
class ITicketService(Protocol):
    def search_issues(self, jql: str, max_results: int = 10) -> List[Dict]: ...
    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "Medium",
        labels: List[str] = None,
    ) -> Dict: ...


@runtime_checkable
class IMetadataService(Protocol):
    def search_assets(self, name: str) -> List[Dict]: ...
    def get_asset(self, asset_id: str) -> Dict: ...
    def get_data_quality(self, asset_id: str) -> Dict: ...


@runtime_checkable
class IVectorService(Protocol):
    def similarity_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]: ...
