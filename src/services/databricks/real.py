"""Real Databricks service."""
from __future__ import annotations

import os
from typing import Dict, List


class DatabricksService:
    def __init__(self, config=None):
        self.host = os.getenv("DATABRICKS_HOST", "")
        self.token = os.getenv("DATABRICKS_TOKEN", "")
        self.http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
        if not all([self.host, self.token, self.http_path]):
            raise EnvironmentError(
                "DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH are required"
            )

    def query(self, sql: str) -> List[Dict]:
        from databricks import sql as dbsql
        with dbsql.connect(
            server_hostname=self.host,
            http_path=self.http_path,
            access_token=self.token,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
