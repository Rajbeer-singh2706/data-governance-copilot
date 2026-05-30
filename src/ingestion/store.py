"""pgvector upsert with SHA-256 dedup."""
from __future__ import annotations

import os
from typing import List

import psycopg2
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector


def upsert_chunks(chunks: List[Document], embeddings: List[List[float]], config=None) -> int:
    host = getattr(config, "host", None) or os.getenv("POSTGRES_HOST", "localhost")
    port = getattr(config, "port", None) or int(os.getenv("POSTGRES_PORT", "5432"))
    db = getattr(config, "database", None) or os.getenv("POSTGRES_DB", "governance_db")
    user = getattr(config, "user", None) or os.getenv("POSTGRES_USER", "postgres")
    password = getattr(config, "password", None) or os.getenv("POSTGRES_PASSWORD", "")

    existing_hashes: set = set()
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata->>'content_hash' FROM langchain_pg_embedding "
                "WHERE metadata->>'content_hash' IS NOT NULL"
            )
            existing_hashes = {row[0] for row in cur.fetchall()}
        conn.close()
    except Exception:
        existing_hashes = set()

    new_chunks, new_embeddings = [], []
    for chunk, emb in zip(chunks, embeddings):
        if chunk.metadata.get("content_hash", "") not in existing_hashes:
            new_chunks.append(chunk)
            new_embeddings.append(emb)

    if not new_chunks:
        return 0

    model = os.getenv("INGESTION_EMBEDDING_MODEL", "text-embedding-3-small")
    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    store = PGVector(embeddings=OpenAIEmbeddings(model=model), collection_name="governance_docs", connection=conn_str)
    store.add_embeddings(
        texts=[c.page_content for c in new_chunks],
        embeddings=new_embeddings,
        metadatas=[c.metadata for c in new_chunks],
    )
    return len(new_chunks)
