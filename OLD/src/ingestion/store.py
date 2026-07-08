"""pgvector upsert with SHA-256 dedup — Neon-compatible."""
from __future__ import annotations

import os
from typing import List
from urllib.parse import urlparse

import psycopg2
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector


def _psycopg2_kwargs() -> dict:
    """Return psycopg2.connect kwargs. Prefers DATABASE_URL (Neon)."""
    raw = os.getenv("DATABASE_URL", "")
    if raw:
        p = urlparse(raw)
        kw = dict(
            host=p.hostname,
            port=p.port or 5432,
            dbname=(p.path or "/governance_db").lstrip("/"),
            user=p.username,
            password=p.password,
            sslmode="require",
        )
        return kw
    return dict(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "governance_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
    )


def _sqlalchemy_conn_str() -> str:
    raw = os.getenv("DATABASE_URL", "")
    if raw:
        raw = raw.replace("postgresql://", "postgresql+psycopg2://")
        raw = raw.replace("postgres://", "postgresql+psycopg2://")
        if "sslmode" not in raw:
            raw += "?sslmode=require"
        return raw
    kw = _psycopg2_kwargs()
    return (
        f"postgresql+psycopg2://{kw['user']}:{kw['password']}"
        f"@{kw['host']}:{kw['port']}/{kw['dbname']}?sslmode={kw['sslmode']}"
    )


def upsert_chunks(chunks: List[Document], embeddings: List[List[float]], config=None) -> int:
    # Allow config override but prefer env / DATABASE_URL
    existing_hashes: set = set()
    try:
        conn = psycopg2.connect(**_psycopg2_kwargs())
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
    collection = os.getenv("VECTOR_COLLECTION", "governance_docs")
    store = PGVector(
        embeddings=OpenAIEmbeddings(model=model),
        collection_name=collection,
        connection=_sqlalchemy_conn_str(),
        use_jsonb=True,
    )
    store.add_embeddings(
        texts=[c.page_content for c in new_chunks],
        embeddings=new_embeddings,
        metadatas=[c.metadata for c in new_chunks],
    )
    return len(new_chunks)
