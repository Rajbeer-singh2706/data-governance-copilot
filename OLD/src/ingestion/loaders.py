"""Document loaders dispatcher."""
from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    TextLoader,
)


def load_document(path: str) -> List[Document]:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(path)
    elif ext == ".docx":
        loader = Docx2txtLoader(path)
    elif ext == ".pptx":
        loader = UnstructuredPowerPointLoader(path)
    elif ext in (".xlsx", ".xls"):
        loader = UnstructuredExcelLoader(path)
    elif ext in (".txt", ".md"):
        loader = TextLoader(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext!r} for path {path!r}")

    docs = loader.load()
    for doc in docs:
        doc.metadata.setdefault("source", path)
    return docs
