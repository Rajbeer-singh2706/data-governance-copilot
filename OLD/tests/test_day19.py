"""
Day 19 tests — ingestion pipeline unit tests.
All tests use mocks/fixtures; no real DB, S3, or OpenAI calls.
"""
import hashlib
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


# ── loaders ───────────────────────────────────────────────────────────────────

class TestLoadDocument:
    def test_unsupported_extension_raises(self):
        from src.ingestion.loaders import load_document
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_document("file.xyz")

    @patch("src.ingestion.loaders.TextLoader")
    def test_txt_uses_text_loader(self, mock_loader_cls):
        mock_loader = MagicMock()
        mock_loader.load.return_value = [Document(page_content="hello", metadata={"source": "file.txt"})]
        mock_loader_cls.return_value = mock_loader

        from src.ingestion.loaders import load_document
        docs = load_document("file.txt")

        assert len(docs) == 1
        assert docs[0].metadata["source"] == "file.txt"

    @patch("src.ingestion.loaders.PyPDFLoader")
    def test_pdf_uses_pypdf_loader(self, mock_loader_cls):
        mock_loader = MagicMock()
        mock_loader.load.return_value = [Document(page_content="pdf content", metadata={})]
        mock_loader_cls.return_value = mock_loader

        from src.ingestion.loaders import load_document
        docs = load_document("report.pdf")

        mock_loader_cls.assert_called_once_with("report.pdf")
        assert len(docs) == 1

    @patch("src.ingestion.loaders.Docx2txtLoader")
    def test_docx_uses_docx_loader(self, mock_loader_cls):
        mock_loader = MagicMock()
        mock_loader.load.return_value = [Document(page_content="word content", metadata={})]
        mock_loader_cls.return_value = mock_loader

        from src.ingestion.loaders import load_document
        docs = load_document("document.docx")
        mock_loader_cls.assert_called_once_with("document.docx")

    def test_source_metadata_added(self):
        from src.ingestion.loaders import load_document
        with patch("src.ingestion.loaders.TextLoader") as mock_cls:
            mock_loader = MagicMock()
            # Doc with no source metadata
            mock_loader.load.return_value = [Document(page_content="text", metadata={})]
            mock_cls.return_value = mock_loader

            docs = load_document("myfile.txt")
            assert docs[0].metadata["source"] == "myfile.txt"


# ── chunker ───────────────────────────────────────────────────────────────────

class TestChunkDocuments:
    def _make_doc(self, content: str, source: str = "retention_policy.pdf") -> Document:
        return Document(page_content=content, metadata={"source": source})

    def test_basic_chunking(self):
        from src.ingestion.chunker import chunk_documents
        long_text = "Data governance " * 100  # > 512 chars
        docs = [self._make_doc(long_text)]
        chunks = chunk_documents(docs, chunk_size=64, chunk_overlap=8)
        assert len(chunks) > 1

    def test_content_hash_added(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("Short governance policy text.")]
        chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=64)
        for chunk in chunks:
            assert "content_hash" in chunk.metadata
            expected = hashlib.sha256(chunk.page_content.encode()).hexdigest()
            assert chunk.metadata["content_hash"] == expected

    def test_chunk_index_added(self):
        from src.ingestion.chunker import chunk_documents
        long_text = "Governance rule " * 200
        docs = [self._make_doc(long_text)]
        chunks = chunk_documents(docs, chunk_size=64, chunk_overlap=8)
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_product_inferred_from_filename(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("retention metrics content", source="retention_report.pdf")]
        chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=64)
        assert chunks[0].metadata["product"] == "retention"

    def test_product_general_for_unknown(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("some content", source="unknown_file.txt")]
        chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=64)
        assert chunks[0].metadata["product"] == "general"

    def test_ltv_product_inferred(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("ltv analysis", source="customer_ltv_2024.pdf")]
        chunks = chunk_documents(docs)
        assert chunks[0].metadata["product"] == "ltv"

    def test_source_preserved(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("text", source="/docs/bookings_q4.pdf")]
        chunks = chunk_documents(docs)
        assert chunks[0].metadata["source"] == "/docs/bookings_q4.pdf"

    def test_empty_docs_returns_empty(self):
        from src.ingestion.chunker import chunk_documents
        chunks = chunk_documents([])
        assert chunks == []

    def test_topic_set_from_filename(self):
        from src.ingestion.chunker import chunk_documents
        docs = [self._make_doc("content", source="cac_metrics_report.pdf")]
        chunks = chunk_documents(docs)
        assert "cac" in chunks[0].metadata["topic"]


# ── embedder ──────────────────────────────────────────────────────────────────

class TestEmbedChunks:
    def test_embed_returns_parallel_vectors(self):
        from src.ingestion.embedder import embed_chunks

        chunks = [
            Document(page_content="governance policy one", metadata={}),
            Document(page_content="data quality rules", metadata={}),
            Document(page_content="retention metrics", metadata={}),
        ]
        fake_vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

        with patch("src.ingestion.embedder.OpenAIEmbeddings") as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.embed_documents.return_value = fake_vectors
            mock_emb_cls.return_value = mock_emb

            embeddings = embed_chunks(chunks)

        assert len(embeddings) == 3
        assert len(embeddings[0]) == 1536

    def test_embed_batches_correctly(self):
        from src.ingestion.embedder import embed_chunks
        import os

        # Create 5 chunks with batch_size=2 → 3 batches
        chunks = [Document(page_content=f"text {i}", metadata={}) for i in range(5)]
        fake_batch = [[float(i)] * 1536 for i in range(5)]

        with patch("src.ingestion.embedder.OpenAIEmbeddings") as mock_cls:
            mock_emb = MagicMock()
            # Return batch-sized slices
            mock_emb.embed_documents.side_effect = lambda batch: [[0.0] * 1536 for _ in batch]
            mock_cls.return_value = mock_emb

            with patch.dict(os.environ, {"INGESTION_BATCH_SIZE": "2"}):
                embeddings = embed_chunks(chunks)

        assert len(embeddings) == 5
        # Should have called embed_documents 3 times (2+2+1)
        assert mock_emb.embed_documents.call_count == 3

    def test_empty_chunks_returns_empty(self):
        from src.ingestion.embedder import embed_chunks
        with patch("src.ingestion.embedder.OpenAIEmbeddings") as mock_cls:
            mock_emb = MagicMock()
            mock_emb.embed_documents.return_value = []
            mock_cls.return_value = mock_emb
            result = embed_chunks([])
        assert result == []


# ── store ─────────────────────────────────────────────────────────────────────

class TestUpsertChunks:
    def _make_chunks(self, n: int = 3) -> list:
        chunks = []
        for i in range(n):
            h = hashlib.sha256(f"text {i}".encode()).hexdigest()
            chunks.append(
                Document(
                    page_content=f"text {i}",
                    metadata={"content_hash": h, "source": f"doc{i}.pdf", "product": "retention"},
                )
            )
        return chunks

    def test_all_new_chunks_inserted(self):
        from src.ingestion.store import upsert_chunks

        chunks = self._make_chunks(3)
        embeddings = [[0.1] * 1536] * 3

        with patch("src.ingestion.store.psycopg2") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):

            # No existing hashes in DB
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_pg.connect.return_value = mock_conn

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            inserted = upsert_chunks(chunks, embeddings)

        assert inserted == 3
        mock_store.add_embeddings.assert_called_once()

    def test_duplicate_chunks_skipped(self):
        from src.ingestion.store import upsert_chunks

        chunks = self._make_chunks(3)
        embeddings = [[0.1] * 1536] * 3

        # Mark all hashes as already existing
        existing = [(c.metadata["content_hash"],) for c in chunks]

        with patch("src.ingestion.store.psycopg2") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = existing
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_pg.connect.return_value = mock_conn

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            inserted = upsert_chunks(chunks, embeddings)

        assert inserted == 0
        mock_store.add_embeddings.assert_not_called()

    def test_partial_dedup(self):
        from src.ingestion.store import upsert_chunks

        chunks = self._make_chunks(4)
        embeddings = [[0.1] * 1536] * 4

        # First 2 are already in DB
        existing = [(chunks[0].metadata["content_hash"],), (chunks[1].metadata["content_hash"],)]

        with patch("src.ingestion.store.psycopg2") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = existing
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_pg.connect.return_value = mock_conn

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            inserted = upsert_chunks(chunks, embeddings)

        assert inserted == 2

    def test_db_error_on_hash_check_gracefully_inserts_all(self):
        from src.ingestion.store import upsert_chunks

        chunks = self._make_chunks(2)
        embeddings = [[0.1] * 1536] * 2

        with patch("src.ingestion.store.psycopg2") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):

            # Simulate DB connection failure on hash check
            mock_pg.connect.side_effect = Exception("connection refused")

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            # Should not raise — treat all as new
            inserted = upsert_chunks(chunks, embeddings)

        assert inserted == 2


# ── pipeline integration (unit-level) ─────────────────────────────────────────

class TestPipelineIntegration:
    """Smoke-test the load→chunk→embed→store pipeline end-to-end with mocks."""

    def test_full_pipeline_smoke(self):
        from src.ingestion.chunker import chunk_documents
        from src.ingestion.embedder import embed_chunks
        from src.ingestion.store import upsert_chunks

        # Simulate what load_document would return
        docs = [
            Document(
                page_content="Retention rate is a key governance metric tracked monthly.",
                metadata={"source": "retention_policy.pdf"},
            )
        ]

        chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=64)
        assert len(chunks) >= 1
        assert all("content_hash" in c.metadata for c in chunks)
        assert all(c.metadata["product"] == "retention" for c in chunks)

        embeddings = [[0.1] * 1536 for _ in chunks]

        with patch("src.ingestion.store.psycopg2") as mock_pg, \
             patch("src.ingestion.store.PGVector") as mock_pgv, \
             patch("src.ingestion.store.OpenAIEmbeddings"):

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_pg.connect.return_value = mock_conn

            mock_store = MagicMock()
            mock_pgv.return_value = mock_store

            inserted = upsert_chunks(chunks, embeddings)

        assert inserted == len(chunks)