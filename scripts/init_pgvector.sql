-- scripts/init_pgvector.sql
-- Day 18: One-time setup for pgvector in governance_db.
--
-- Run once on your PostgreSQL instance:
--   psql postgresql://user:pass@host:5432/governance_db < scripts/init_pgvector.sql
--
-- Or via Docker Compose:
--   docker-compose exec postgres psql -U postgres -d governance_db \
--     -f /scripts/init_pgvector.sql

-- ── 1. Enable pgvector extension ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- for gen_random_uuid()



-- ── 2. Document embeddings table ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_embeddings (
    id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    collection   TEXT          NOT NULL,           -- e.g. "governance_docs"
    document     TEXT          NOT NULL,           -- raw document text
    metadata     JSONB         DEFAULT '{}',        -- product, topic, source, etc.
    embedding    vector(1536),                      -- text-embedding-3-small dim
    created_at   TIMESTAMPTZ   DEFAULT NOW(),
    updated_at   TIMESTAMPTZ   DEFAULT NOW()
);

-- ── 3. IVFFlat index for fast ANN search ─────────────────────────────────
-- lists=100 is a good default for up to ~1M vectors.
-- Rebuild index if total row count grows by 10× (REINDEX TABLE document_embeddings).
CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
    ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── 4. Metadata index for filtering ──────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_embeddings_metadata
    ON document_embeddings USING gin (metadata);

CREATE INDEX IF NOT EXISTS idx_embeddings_collection
    ON document_embeddings (collection);

-- ── 5. Auto-update updated_at on row changes ─────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_updated_at ON document_embeddings;
CREATE TRIGGER trg_updated_at
    BEFORE UPDATE ON document_embeddings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 6. Verify ─────────────────────────────────────────────────────────────
DO $$
BEGIN
    RAISE NOTICE 'pgvector setup complete.';
    RAISE NOTICE 'Table: document_embeddings';
    RAISE NOTICE 'Index: ivfflat (vector_cosine_ops, lists=100)';
    RAISE NOTICE 'Ready for langchain-postgres PGVector.';
END;
$$;


-- One-time pgvector database setup
-- Run: psql -U postgres -d governance_db -f scripts/init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- langchain_postgres creates this table automatically on first use,
-- but we ensure the extension and schema exist.
CREATE SCHEMA IF NOT EXISTS public;

-- Optional: pre-create the embeddings table for visibility
-- langchain_postgres will manage the actual schema via PGVector.create_tables_if_not_exists()
-- This is a no-op if table already exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'langchain_pg_embedding'
    ) THEN
        RAISE NOTICE 'Table langchain_pg_embedding will be created by langchain_postgres on first use.';
    ELSE
        RAISE NOTICE 'Table langchain_pg_embedding already exists.';
    END IF;
END
$$;

-- Create airflow DB (separate from governance_db)
-- Run this as superuser before starting Airflow:
-- CREATE DATABASE airflow_db;