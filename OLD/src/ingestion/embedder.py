"""Embedding using OpenAI text-embedding-3-small."""
from __future__ import annotations

import os
from typing import List

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


def embed_chunks(chunks: List[Document]) -> List[List[float]]:
    model = os.getenv("INGESTION_EMBEDDING_MODEL", "text-embedding-3-small")
    batch_size = int(os.getenv("INGESTION_BATCH_SIZE", "100"))
    embedder = OpenAIEmbeddings(model=model)
    texts = [c.page_content for c in chunks]
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        embeddings.extend(embedder.embed_documents(texts[i:i + batch_size]))
    return embeddings
