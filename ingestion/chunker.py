"""Chunking utilities for the RAG ingestion pipeline."""
import hashlib
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


_PRODUCT_KEYWORDS = {
    "retention": "retention",
    "bookings": "bookings",
    "cac": "cac",
    "ltv": "ltv",
    "customer_ltv": "ltv",
    "revenue": "bookings",
}


def _infer_product(source: str) -> str:
    """Infer data product from filename."""
    name = Path(source).stem.lower()
    for keyword, product in _PRODUCT_KEYWORDS.items():
        if keyword in name:
            return product
    return "general"


def _infer_topic(source: str) -> str:
    """Infer topic from filename."""
    name = Path(source).stem.lower().replace("_", " ").replace("-", " ")
    return name


def chunk_documents(
    docs: List[Document],
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[Document]:
    """
    Split documents into chunks and enrich metadata.

    Metadata fields added per chunk:
      - source       (inherited from doc)
      - product      (inferred from filename)
      - topic        (inferred from filename)
      - chunk_index  (0-based within the source document)
      - content_hash (SHA-256 of chunk text — dedup key)
    """
    chunk_size = chunk_size or int(os.getenv("INGESTION_CHUNK_SIZE", "512"))
    chunk_overlap = chunk_overlap or int(os.getenv("INGESTION_CHUNK_OVERLAP", "64"))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks: List[Document] = []

    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        product = _infer_product(source)
        topic = _infer_topic(source)

        sub_chunks = splitter.split_documents([doc])

        for idx, chunk in enumerate(sub_chunks):
            content_hash = hashlib.sha256(chunk.page_content.encode()).hexdigest()
            chunk.metadata.update(
                {
                    "source": source,
                    "product": product,
                    "topic": topic,
                    "chunk_index": idx,
                    "content_hash": content_hash,
                }
            )
            chunks.append(chunk)

    return chunks