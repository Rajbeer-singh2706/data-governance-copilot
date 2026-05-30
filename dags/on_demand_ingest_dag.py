"""
Airflow DAG: on_demand_ingest_dag
Triggered via REST API (POST /ingest or Airflow REST) with conf.filepath.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-governance",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="on_demand_ingest_dag",
    default_args=default_args,
    description="Ingest a single file on demand (conf.filepath)",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "rag", "on-demand"],
) as dag:

    def _load_single(**context):
        from src.ingestion.loaders import load_document

        filepath = context["dag_run"].conf.get("filepath")
        if not filepath:
            raise ValueError("conf.filepath is required for on_demand_ingest_dag")

        docs = load_document(filepath)
        print(f"Loaded {len(docs)} pages from {filepath}")
        context["ti"].xcom_push(key="filepath", value=filepath)
        context["ti"].xcom_push(key="doc_count", value=len(docs))
        return len(docs)

    def _chunk(**context):
        from src.ingestion.loaders import load_document
        from src.ingestion.chunker import chunk_documents

        filepath = context["dag_run"].conf.get("filepath")
        docs = load_document(filepath)
        chunks = chunk_documents(docs)
        print(f"Created {len(chunks)} chunks from {filepath}")
        context["ti"].xcom_push(key="chunk_count", value=len(chunks))
        return len(chunks)

    def _embed(**context):
        from src.ingestion.loaders import load_document
        from src.ingestion.chunker import chunk_documents
        from src.ingestion.embedder import embed_chunks

        filepath = context["dag_run"].conf.get("filepath")
        docs = load_document(filepath)
        chunks = chunk_documents(docs)
        embeddings = embed_chunks(chunks)
        print(f"Embedded {len(embeddings)} chunks")
        return len(embeddings)

    def _store(**context):
        from src.ingestion.loaders import load_document
        from src.ingestion.chunker import chunk_documents
        from src.ingestion.embedder import embed_chunks
        from src.ingestion.store import upsert_chunks

        filepath = context["dag_run"].conf.get("filepath")
        docs = load_document(filepath)
        chunks = chunk_documents(docs)
        embeddings = embed_chunks(chunks)
        inserted = upsert_chunks(chunks, embeddings)
        print(f"Upserted {inserted} new chunks")
        return inserted

    load_single = PythonOperator(task_id="load_single", python_callable=_load_single)
    chunk = PythonOperator(task_id="chunk", python_callable=_chunk)
    embed = PythonOperator(task_id="embed", python_callable=_embed)
    store = PythonOperator(task_id="store", python_callable=_store)

    load_single >> chunk >> embed >> store