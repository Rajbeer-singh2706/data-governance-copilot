"""pgvector upsert with SHA-256 dedup for the RAG ingestion pipeline."""
import os
from typing import List

from langchain_core.documents import Document


def upsert_chunks(
    chunks: List[Document],
    embeddings: List[List[float]],
    config=None,
) -> int:
    """
    Upsert chunks into pgvector, skipping duplicates by content_hash.

    Args:
        chunks:     List of Document chunks (with content_hash in metadata)
        embeddings: Parallel list of embedding vectors
        config:     VectorDBConfig (optional; reads env vars if None)

    Returns:
        Number of newly inserted chunks (0 = all duplicates skipped)
    """
    import psycopg2
    from langchain_postgres import PGVector
    from langchain_openai import OpenAIEmbeddings

    # Build connection string
    if config is not None:
        host = config.host
        port = config.port
        db = config.database
        user = config.user
        password = config.password
    else:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        db = os.getenv("POSTGRES_DB", "governance_db")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")

    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

    # Fetch existing hashes to detect duplicates
    existing_hashes: set = set()
    try:
        raw_conn = psycopg2.connect(
            host=host, port=port, dbname=db, user=user, password=password
        )
        with raw_conn.cursor() as cur:
            cur.execute(
                "SELECT metadata->>'content_hash' FROM langchain_pg_embedding "
                "WHERE metadata->>'content_hash' IS NOT NULL"
            )
            rows = cur.fetchall()
            existing_hashes = {row[0] for row in rows}
        raw_conn.close()
    except Exception:
        # Table may not exist yet — first run
        existing_hashes = set()

    # Filter out duplicates
    new_chunks: List[Document] = []
    new_embeddings: List[List[float]] = []

    for chunk, emb in zip(chunks, embeddings):
        h = chunk.metadata.get("content_hash", "")
        if h not in existing_hashes:
            new_chunks.append(chunk)
            new_embeddings.append(emb)

    if not new_chunks:
        return 0

    # Upsert via PGVector
    model = os.getenv("INGESTION_EMBEDDING_MODEL", "text-embedding-3-small")
    embedder = OpenAIEmbeddings(model=model)

    vector_store = PGVector(
        embeddings=embedder,
        collection_name="governance_docs",
        connection=conn_str,
    )
    vector_store.add_embeddings(
        texts=[c.page_content for c in new_chunks],
        embeddings=new_embeddings,
        metadatas=[c.metadata for c in new_chunks],
    )

    return len(new_chunks)