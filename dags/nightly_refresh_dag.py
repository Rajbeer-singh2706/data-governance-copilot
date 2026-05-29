"""
Airflow DAG: nightly_refresh_dag
Nightly at 02:00 UTC — re-embeds changed chunks, prunes deleted files.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

DOCS_PATH = os.getenv("AIRFLOW_DOCS_PATH", "./docs")

default_args = {
    "owner": "data-governance",
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

with DAG(
    dag_id="nightly_refresh_dag",
    default_args=default_args,
    description="Nightly hash-diff re-embed of changed docs + prune deleted",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "rag", "refresh"],
) as dag:

    def _scan_docs(**context):
        """Scan docs/ folder and compute SHA-256 hashes of file contents."""
        import glob
        import hashlib

        pattern = os.path.join(DOCS_PATH, "**", "*.*")
        files = glob.glob(pattern, recursive=True)

        file_hashes = {}
        for path in files:
            try:
                with open(path, "rb") as f:
                    file_hashes[path] = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                pass

        context["ti"].xcom_push(key="file_hashes", value=file_hashes)
        print(f"Scanned {len(file_hashes)} files")
        return len(file_hashes)

    def _diff_hashes(**context):
        """Compare file hashes against stored chunk hashes to find changed files."""
        import psycopg2

        file_hashes: dict = context["ti"].xcom_pull(task_ids="scan_docs", key="file_hashes")

        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        db = os.getenv("POSTGRES_DB", "governance_db")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")

        try:
            conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT metadata->>'source', metadata->>'content_hash' "
                    "FROM langchain_pg_embedding WHERE metadata->>'source' IS NOT NULL"
                )
                db_records = cur.fetchall()
            conn.close()

            # Build set of (source, hash) pairs already in DB
            db_hashes = {row[0]: row[1] for row in db_records}
        except Exception as e:
            print(f"DB check failed (first run?): {e}")
            db_hashes = {}

        # Find files whose content has changed
        changed_files = []
        for path, file_hash in file_hashes.items():
            stored_hash = db_hashes.get(path)
            if stored_hash != file_hash:
                changed_files.append(path)

        # Find sources in DB that no longer exist on disk
        deleted_sources = [
            src for src in db_hashes.keys()
            if src not in file_hashes and not src.startswith("collibra://")
        ]

        context["ti"].xcom_push(key="changed_files", value=changed_files)
        context["ti"].xcom_push(key="deleted_sources", value=deleted_sources)
        print(f"Changed files: {len(changed_files)}, Deleted sources: {len(deleted_sources)}")
        return len(changed_files)

    def _re_embed_delta(**context):
        """Re-embed only changed files."""
        from ingestion.loaders import load_document
        from ingestion.chunker import chunk_documents
        from ingestion.embedder import embed_chunks

        changed_files: list = context["ti"].xcom_pull(task_ids="diff_hashes", key="changed_files")

        if not changed_files:
            print("No changed files — skipping re-embed")
            context["ti"].xcom_push(key="new_chunks", value=[])
            context["ti"].xcom_push(key="new_embeddings", value=[])
            return 0

        all_chunks = []
        for path in changed_files:
            try:
                docs = load_document(path)
                chunks = chunk_documents(docs)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Failed to load {path}: {e}")

        embeddings = embed_chunks(all_chunks) if all_chunks else []

        # Serialize chunks for XCom
        serialized = [
            {"page_content": c.page_content, "metadata": c.metadata}
            for c in all_chunks
        ]
        context["ti"].xcom_push(key="new_chunks_serialized", value=serialized)
        context["ti"].xcom_push(key="new_embeddings", value=embeddings)
        print(f"Re-embedded {len(all_chunks)} chunks from {len(changed_files)} changed files")
        return len(all_chunks)

    def _upsert(**context):
        """Upsert newly embedded chunks."""
        from langchain_core.documents import Document
        from ingestion.store import upsert_chunks

        serialized = context["ti"].xcom_pull(task_ids="re_embed_delta", key="new_chunks_serialized") or []
        embeddings = context["ti"].xcom_pull(task_ids="re_embed_delta", key="new_embeddings") or []

        if not serialized:
            print("Nothing to upsert")
            return 0

        chunks = [
            Document(page_content=d["page_content"], metadata=d["metadata"])
            for d in serialized
        ]
        inserted = upsert_chunks(chunks, embeddings)
        print(f"Upserted {inserted} refreshed chunks")
        return inserted

    def _prune_deleted(**context):
        """Remove chunks from pgvector for deleted source files."""
        import psycopg2

        deleted_sources: list = context["ti"].xcom_pull(task_ids="diff_hashes", key="deleted_sources") or []

        if not deleted_sources:
            print("No deleted sources to prune")
            return 0

        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        db = os.getenv("POSTGRES_DB", "governance_db")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")

        pruned = 0
        try:
            conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
            with conn.cursor() as cur:
                for source in deleted_sources:
                    cur.execute(
                        "DELETE FROM langchain_pg_embedding WHERE metadata->>'source' = %s",
                        (source,),
                    )
                    pruned += cur.rowcount
            conn.commit()
            conn.close()
            print(f"Pruned {pruned} chunks from {len(deleted_sources)} deleted sources")
        except Exception as e:
            print(f"Prune failed: {e}")

        return pruned

    scan_docs = PythonOperator(task_id="scan_docs", python_callable=_scan_docs)
    diff_hashes = PythonOperator(task_id="diff_hashes", python_callable=_diff_hashes)
    re_embed_delta = PythonOperator(task_id="re_embed_delta", python_callable=_re_embed_delta)
    upsert = PythonOperator(task_id="upsert", python_callable=_upsert)
    prune_deleted = PythonOperator(task_id="prune_deleted", python_callable=_prune_deleted)

    scan_docs >> diff_hashes >> [re_embed_delta, prune_deleted]
    re_embed_delta >> upsert