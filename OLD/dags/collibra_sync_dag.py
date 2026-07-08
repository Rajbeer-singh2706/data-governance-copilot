"""
Airflow DAG: collibra_sync_dag
Pulls Collibra asset catalog daily at 06:00 UTC → embed → upsert into pgvector.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-governance",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="collibra_sync_dag",
    default_args=default_args,
    description="Daily Collibra asset sync into pgvector",
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "collibra", "governance"],
) as dag:

    def _fetch_collibra(**context):
        """Pull assets from Collibra REST API (or mock)."""
        import os

        enable_mock = os.getenv("ENABLE_MOCK", "true").lower() == "true"

        if enable_mock:
            # Return canned assets for dev/test
            assets = [
                {
                    "id": "asset-001",
                    "name": "retention_metrics",
                    "domain": "Customer Success",
                    "status": "Approved",
                    "owner": "cs-team@company.com",
                    "description": "Monthly customer retention rates and cohort analysis.",
                    "product": "retention",
                },
                {
                    "id": "asset-002",
                    "name": "bookings_fact",
                    "domain": "Revenue Operations",
                    "status": "Approved",
                    "owner": "revops@company.com",
                    "description": "Bookings and ARR metrics by segment and quarter.",
                    "product": "bookings",
                },
                {
                    "id": "asset-003",
                    "name": "cac_metrics",
                    "domain": "Marketing Analytics",
                    "status": "Approved",
                    "owner": "marketing@company.com",
                    "description": "Customer acquisition cost by channel and campaign.",
                    "product": "cac",
                },
                {
                    "id": "asset-004",
                    "name": "customer_ltv",
                    "domain": "Data Science",
                    "status": "Approved",
                    "owner": "ds@company.com",
                    "description": "Lifetime value predictions and cohort LTV analysis.",
                    "product": "ltv",
                },
            ]
        else:
            import requests
            base_url = os.getenv("COLLIBRA_BASE_URL", "")
            username = os.getenv("COLLIBRA_USERNAME", "")
            password = os.getenv("COLLIBRA_PASSWORD", "")
            resp = requests.get(
                f"{base_url}/rest/2.0/assets",
                auth=(username, password),
                params={"limit": 100},
                timeout=30,
            )
            resp.raise_for_status()
            assets = resp.json().get("results", [])

        context["ti"].xcom_push(key="assets", value=assets)
        print(f"Fetched {len(assets)} assets from Collibra")
        return len(assets)

    def _format_as_documents(**context):
        """Convert Collibra assets into LangChain Documents."""
        from langchain_core.documents import Document
        import json

        assets = context["ti"].xcom_pull(task_ids="fetch_collibra", key="assets")

        docs = []
        for asset in assets:
            content = (
                f"Asset: {asset.get('name', '')}\n"
                f"Domain: {asset.get('domain', '')}\n"
                f"Status: {asset.get('status', '')}\n"
                f"Owner: {asset.get('owner', '')}\n"
                f"Description: {asset.get('description', '')}"
            )
            doc = Document(
                page_content=content,
                metadata={
                    "source": f"collibra://{asset.get('id', '')}",
                    "product": asset.get("product", "general"),
                    "topic": asset.get("name", ""),
                    "asset_id": asset.get("id", ""),
                },
            )
            docs.append(doc)

        # Serialize for XCom (Documents aren't JSON-serializable natively)
        serialized = [
            {"page_content": d.page_content, "metadata": d.metadata} for d in docs
        ]
        context["ti"].xcom_push(key="docs", value=serialized)
        print(f"Formatted {len(docs)} documents")
        return len(docs)

    def _embed_and_upsert(**context):
        from langchain_core.documents import Document
        from src.ingestion.chunker import chunk_documents
        from src.ingestion.embedder import embed_chunks
        from src.ingestion.store import upsert_chunks

        serialized = context["ti"].xcom_pull(task_ids="format_as_documents", key="docs")
        docs = [
            Document(page_content=d["page_content"], metadata=d["metadata"])
            for d in serialized
        ]

        chunks = chunk_documents(docs)
        embeddings = embed_chunks(chunks)
        inserted = upsert_chunks(chunks, embeddings)
        print(f"Upserted {inserted} new Collibra chunks")
        return inserted

    fetch_collibra = PythonOperator(task_id="fetch_collibra", python_callable=_fetch_collibra)
    format_as_documents = PythonOperator(task_id="format_as_documents", python_callable=_format_as_documents)
    embed_and_upsert = PythonOperator(task_id="embed_and_upsert", python_callable=_embed_and_upsert)

    fetch_collibra >> format_as_documents >> embed_and_upsert