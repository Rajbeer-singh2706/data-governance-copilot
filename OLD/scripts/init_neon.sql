-- ============================================================
-- Neon PostgreSQL initialisation for Data Governance Copilot
-- Run this once against your Neon database with:
--   psql "$DATABASE_URL" -f scripts/init_neon.sql
-- ============================================================

-- pgvector extension (Neon has it pre-installed, but just in case)
CREATE EXTENSION IF NOT EXISTS vector;

-- LangChain / PGVector managed tables are created automatically by
-- langchain_postgres when you first call PGVector(..., create_tables=True).
-- The SQL below creates the supporting tables for the Copilot itself.

-- ── LangGraph PostgresSaver tables ─────────────────────────────────────────
-- These are auto-created by PostgresSaver.setup(); included here for reference.
-- CREATE TABLE IF NOT EXISTS checkpoints (...);
-- CREATE TABLE IF NOT EXISTS checkpoint_writes (...);

-- ── Application tables ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS governance_rules (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    condition   TEXT NOT NULL,
    product     TEXT DEFAULT 'general',
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,
    user_id     TEXT,
    thread_id   TEXT,
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_thread ON audit_log(thread_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event  ON audit_log(event_type);

-- HNSW index on the vector column (created after langchain_pg_embedding exists)
-- Run this after your first document ingestion:
-- CREATE INDEX IF NOT EXISTS hnsw_embedding_idx
--     ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

\echo 'Neon schema initialised successfully.'
