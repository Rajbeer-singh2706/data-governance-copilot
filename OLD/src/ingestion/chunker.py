"""Chunking with metadata enrichment."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

_PRODUCT_KEYWORDS = {
    "retention": "retention", "bookings": "bookings", "cac": "cac",
    "ltv": "ltv", "customer_ltv": "ltv", "revenue": "bookings",
}


def _infer_product(source: str) -> str:
    name = Path(source).stem.lower()
    for keyword, product in _PRODUCT_KEYWORDS.items():
        if keyword in name:
            return product
    return "general"


def chunk_documents(docs: List[Document], chunk_size: int = None, chunk_overlap: int = None) -> List[Document]:
    chunk_size = chunk_size or int(os.getenv("INGESTION_CHUNK_SIZE", "512"))
    chunk_overlap = chunk_overlap or int(os.getenv("INGESTION_CHUNK_OVERLAP", "64"))
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        product = _infer_product(source)
        topic = Path(source).stem.lower().replace("_", " ").replace("-", " ")
        sub = splitter.split_documents([doc])
        for idx, chunk in enumerate(sub):
            content_hash = hashlib.sha256(chunk.page_content.encode()).hexdigest()
            chunk.metadata.update({"source": source, "product": product, "topic": topic,
                                   "chunk_index": idx, "content_hash": content_hash})
            chunks.append(chunk)
    return chunks
