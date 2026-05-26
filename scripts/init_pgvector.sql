-- scripts/init_pgvector.sql  — NEW file (Day 18)
-- Run once: psql $DATABASE_URL < scripts/init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS document_embeddings (
    id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    collection   TEXT          NOT NULL,           -- e.g. "governance_docs"
    document     TEXT          NOT NULL,           -- raw document text
    metadata     JSONB         DEFAULT '{}',       -- product, topic, source
    embedding    vector(1536),                     -- text-embedding-3-small
    created_at   TIMESTAMPTZ   DEFAULT NOW(),
    updated_at   TIMESTAMPTZ   DEFAULT NOW()
);

-- IVFFlat index: fast ANN search (lists=100 good for up to ~1M vectors)
CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
    ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- GIN index on metadata JSON for filtered search
CREATE INDEX IF NOT EXISTS idx_embeddings_metadata
    ON document_embeddings USING gin (metadata);