"""
Airflow DAG: file_ingestion_dag
Watches docs/ folder for new files → load → chunk → embed → upsert.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor

DOCS_PATH = os.getenv("AIRFLOW_DOCS_PATH", "./docs")

default_args = {
    "owner": "data-governance",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="file_ingestion_dag",
    default_args=default_args,
    description="Watches docs/ for new files and ingests them into pgvector",
    schedule=None,  # triggered by FileSensor
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "rag"],
) as dag:

    sense_new_file = FileSensor(
        task_id="sense_new_file",
        filepath=DOCS_PATH,
        poke_interval=30,
        timeout=3600,
        mode="reschedule",
    )

    def _load_docs(**context):
        import glob
        from src.ingestion.loaders import load_document

        pattern = os.path.join(DOCS_PATH, "**", "*.*")
        files = glob.glob(pattern, recursive=True)

        all_docs = []
        loaded_paths = []
        for path in files:
            try:
                docs = load_document(path)
                all_docs.extend(docs)
                loaded_paths.append(path)
                print(f"Loaded {len(docs)} pages from {path}")
            except ValueError as e:
                print(f"Skipping unsupported file {path}: {e}")

        context["ti"].xcom_push(key="doc_count", value=len(all_docs))
        context["ti"].xcom_push(key="loaded_paths", value=loaded_paths)
        return len(all_docs)

    def _chunk_docs(**context):
        import glob
        from src.ingestion.loaders import load_document
        from src.ingestion.chunker import chunk_documents

        pattern = os.path.join(DOCS_PATH, "**", "*.*")
        files = glob.glob(pattern, recursive=True)

        all_docs = []
        for path in files:
            try:
                all_docs.extend(load_document(path))
            except ValueError:
                pass

        chunks = chunk_documents(all_docs)
        context["ti"].xcom_push(key="chunk_count", value=len(chunks))
        print(f"Created {len(chunks)} chunks")
        return len(chunks)

    def _embed_and_store(**context):
        import glob
        from src.ingestion.loaders import load_document
        from src.ingestion.chunker import chunk_documents
        from src.ingestion.embedder import embed_chunks
        from src.ingestion.store import upsert_chunks

        pattern = os.path.join(DOCS_PATH, "**", "*.*")
        files = glob.glob(pattern, recursive=True)

        all_docs = []
        for path in files:
            try:
                all_docs.extend(load_document(path))
            except ValueError:
                pass

        chunks = chunk_documents(all_docs)
        embeddings = embed_chunks(chunks)
        inserted = upsert_chunks(chunks, embeddings)
        print(f"Upserted {inserted} new chunks (duplicates skipped)")
        return inserted

    def _notify(**context):
        inserted = context["ti"].xcom_pull(task_ids="embed_and_store")
        print(f"✅ Ingestion complete. {inserted} new chunks added to pgvector.")

    load_docs = PythonOperator(task_id="load_docs", python_callable=_load_docs)
    chunk = PythonOperator(task_id="chunk", python_callable=_chunk_docs)
    embed_and_store = PythonOperator(task_id="embed_and_store", python_callable=_embed_and_store)
    notify = PythonOperator(task_id="notify", python_callable=_notify)

    sense_new_file >> load_docs >> chunk >> embed_and_store >> notify