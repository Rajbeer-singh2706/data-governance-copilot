"""Document loaders for the RAG ingestion pipeline."""
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document


def load_document(path: str) -> List[Document]:
    """Load a document from disk. Dispatches by file extension."""
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(path)
    elif ext == ".docx":
        from langchain_community.document_loaders import Docx2txtLoader
        loader = Docx2txtLoader(path)
    elif ext == ".pptx":
        from langchain_community.document_loaders import UnstructuredPowerPointLoader
        loader = UnstructuredPowerPointLoader(path)
    elif ext in (".xlsx", ".xls"):
        from langchain_community.document_loaders import UnstructuredExcelLoader
        loader = UnstructuredExcelLoader(path)
    elif ext in (".txt", ".md"):
        from langchain_community.document_loaders import TextLoader
        loader = TextLoader(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext!r} for path {path!r}")

    docs = loader.load()

    # Enrich metadata with source path
    for doc in docs:
        doc.metadata.setdefault("source", path)

    return docs