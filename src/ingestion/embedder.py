"""Embedding utilities for the RAG ingestion pipeline."""
import os
from typing import List

from langchain_core.documents import Document


def embed_chunks(chunks: List[Document]) -> List[List[float]]:
    """
    Embed a list of document chunks using OpenAI text-embedding-3-small.

    Returns a list of 1536-dim float vectors, parallel to input chunks.
    Processes in batches of INGESTION_BATCH_SIZE (default 100).
    """
    from langchain_openai import OpenAIEmbeddings

    model = os.getenv("INGESTION_EMBEDDING_MODEL", "text-embedding-3-small")
    batch_size = int(os.getenv("INGESTION_BATCH_SIZE", "100"))

    embedder = OpenAIEmbeddings(model=model)

    texts = [chunk.page_content for chunk in chunks]
    embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = embedder.embed_documents(batch)
        embeddings.extend(batch_embeddings)

    return embeddings