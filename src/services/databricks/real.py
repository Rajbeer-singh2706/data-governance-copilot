"""
src/services/databricks/real.py
Real Databricks SQL Warehouse connector.

Requires env vars:
  DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH

Raises EnvironmentError at construction if any are missing —
caught by the service factory which falls back to mock.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.logging_utils import with_retry


class DatabricksService:
    """
    Thin wrapper around databricks-sql-connector.
    Satisfies IDataService protocol.
    """

    def __init__(self, config) -> None:
        """
        Args:
            config: DatabricksConfig dataclass from settings.py
        Raises:
            EnvironmentError: if host / token / http_path are not set
        """
        if not config or not config.host:
            raise EnvironmentError(
                "DatabricksService requires DATABRICKS_HOST, "
                "DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH to be set."
            )
        self._config = config
        self._connection = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _connect(self) -> None:
        from databricks import sql as dbsql

        self._connection = dbsql.connect(
            server_hostname=self._config.host,
            http_path=self._config.http_path,
            access_token=self._config.token,
        )

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None

    # ── IDataService ──────────────────────────────────────────────────────

    @with_retry(max_retries=3)
    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL and return rows as list-of-dicts."""
        if not self._connection:
            self._connect()
        with self._connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]