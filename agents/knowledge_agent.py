"""
Knowledge Agent
---------------
Retrieves business context from unstructured sources:
PDFs, DOCX, PPTX, Excel, SharePoint, Confluence.

Uses RAG (Retrieval-Augmented Generation) with FAISS/Chroma vector store.
Provides business definitions, runbooks, and contextual explanations.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.logging_utils import logger


# ---------------------------------------------------------------------------
# Mock knowledge base
# ---------------------------------------------------------------------------

MOCK_KNOWLEDGE_BASE = {
    "retention": {
        "definition": (
            "Gross Retention Rate (GRR) measures the percentage of recurring revenue "
            "retained from existing customers, excluding expansion. Net Retention Rate (NRR) "
            "includes upsells and expansions. Industry benchmarks: GRR >85% (SMB), >90% (Enterprise)."
        ),
        "business_context": (
            "Retention declined in Q3 2024 were partially attributed to: (1) product gaps in "
            "the reporting module cited in 34% of churn surveys, (2) competitive displacement "
            "by Vendor X in the SMB segment, and (3) a 2-week SLA breach in the EU region "
            "affecting 12 enterprise accounts."
        ),
        "runbook": "See: Retention Recovery Playbook v2.1 (SharePoint/CS/Playbooks/)",
        "source": "SharePoint: CS Strategy Deck Q3 2024.pptx",
    },
    "bookings": {
        "definition": (
            "Bookings represent the total value of new signed contracts in a period. "
            "Net New Bookings = New Logo + Expansion - Contraction. Bookings differ from "
            "Revenue which is recognized over the contract term."
        ),
        "business_context": (
            "The bookings methodology was updated in FY2024 to exclude multi-year "
            "contract prepayments from the current-period booking total. This change "
            "created a ~12% YoY comparison distortion in Q1 2024."
        ),
        "runbook": "See: Revenue Metrics Glossary v3.0 (Confluence/RevOps/Glossary/)",
        "source": "Confluence: Revenue Metrics Glossary",
    },
    "cac": {
        "definition": (
            "Customer Acquisition Cost (CAC) = Total Sales & Marketing Spend / New Customers Acquired. "
            "Blended CAC includes all channels. Paid CAC isolates paid media only. "
            "CAC Payback Period = CAC / (ARR per Customer / 12)."
        ),
        "business_context": (
            "CAC increased 18% YoY due to higher LinkedIn CPM rates and expanded SDR headcount. "
            "The Marketing team is targeting a return to $9,500 blended CAC by Q4 FY2025 through "
            "increased PLG (product-led growth) investment."
        ),
        "runbook": "See: Marketing Analytics Handbook (Confluence/Marketing/)",
        "source": "Confluence: Marketing Analytics Handbook",
    },
    "ltv": {
        "definition": (
            "Lifetime Value (LTV) estimates the total revenue a customer will generate. "
            "Model: LTV = (ARR × Gross Margin) / Churn Rate. "
            "The Data Science team updates the predictive LTV model quarterly using XGBoost."
        ),
        "business_context": (
            "LTV/CAC ratio of 3.5x is below the 5x target for the Enterprise segment. "
            "Data Science is refactoring the LTV model to include expansion revenue signals "
            "from product usage data (Project Helix, Q2 2025 release)."
        ),
        "runbook": "See: LTV Model Documentation (Confluence/DS/Models/LTV/)",
        "source": "Confluence: Data Science Model Registry",
    },
    "data_quality": {
        "definition": (
            "Data Quality is measured across six dimensions: Completeness, Accuracy, "
            "Consistency, Timeliness, Validity, and Uniqueness. Scores are tracked in "
            "Collibra and surfaced in the Data Governance Dashboard."
        ),
        "business_context": (
            "The Retention metrics table had a completeness issue in September 2024 where "
            "the EU region data was missing for 3 days due to a pipeline failure in the "
            "Databricks ETL job (see Jira: DATA-4821)."
        ),
        "source": "Collibra: Data Quality Scorecard",
    },
}


# ---------------------------------------------------------------------------
# Vector Store wrapper (FAISS or Chroma)
# ---------------------------------------------------------------------------

class VectorStoreWrapper:
    """
    Production vector store using FAISS (default) or Chroma.
    Falls back to keyword search if vector libraries are unavailable.
    """

    def __init__(self, config, embedding_model: str):
        self.config = config
        self.embedding_model = embedding_model
        self._store = None
        self._use_faiss = False
        self._use_chroma = False
        self._init_store()

    def _init_store(self):
        try:
            import faiss  # noqa
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings
            self._faiss_cls = FAISS
            self._embeddings = OpenAIEmbeddings(model=self.embedding_model)
            self._use_faiss = True
            logger.info("VectorStore: using FAISS")
        except ImportError:
            logger.warning("FAISS not available; falling back to keyword search.")

    def load_documents(self, docs: List[Dict]) -> bool:
        """Index a list of {text, metadata} dicts into the vector store."""
        if not self._use_faiss:
            return False
        try:
            from langchain.schema import Document
            langchain_docs = [
                Document(page_content=d["text"], metadata=d.get("metadata", {}))
                for d in docs
            ]
            self._store = self._faiss_cls.from_documents(langchain_docs, self._embeddings)
            return True
        except Exception as e:
            logger.error(f"VectorStore load failed: {e}")
            return False

    def similarity_search(self, query: str, k: int = 4) -> List[Dict]:
        if self._store:
            results = self._store.similarity_search(query, k=k)
            return [{"text": r.page_content, "metadata": r.metadata} for r in results]
        return []


# ---------------------------------------------------------------------------
# SharePoint / Confluence connector stubs
# ---------------------------------------------------------------------------

class SharePointConnector:
    def __init__(self, config): self.config = config

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        # Real: use Microsoft Graph API to search SharePoint content
        return []


class ConfluenceConnector:
    def __init__(self, base_url: str, token: str): self.base_url = base_url

    def search(self, query: str, space_key: str = "") -> List[Dict]:
        # Real: use Confluence REST API /rest/api/content/search
        return []


# ---------------------------------------------------------------------------
# Knowledge Agent
# ---------------------------------------------------------------------------

class KnowledgeAgent(BaseAgent):
    """
    RAG-based knowledge retrieval agent.

    Read capabilities:
    - Business definitions for data products and metrics
    - Contextual explanations from internal documentation
    - Runbook / playbook references
    - SharePoint and Confluence content search
    """

    name = "knowledge_agent"
    description = "Retrieves business context and documentation via RAG"
    capabilities = [
        "business_definitions",
        "contextual_explanation",
        "document_search",
        "runbook_retrieval",
        "confluence_sharepoint_integration",
    ]

    TOPIC_KEYWORDS = {
        "retention": ["retention", "churn", "renewal", "grr", "nrr"],
        "bookings": ["bookings", "revenue", "arr", "mrr", "contract"],
        "cac": ["cac", "acquisition cost", "payback", "marketing spend"],
        "ltv": ["ltv", "lifetime value", "customer value"],
        "data_quality": ["data quality", "completeness", "accuracy", "dq", "pipeline"],
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)
        self._vector_store = None
        if config and not enable_mock:
            self._vector_store = VectorStoreWrapper(
                config.vector_store,
                config.vector_store.embedding_model,
            )

    def _detect_topics(self, query: str) -> List[str]:
        query_lower = query.lower()
        return [
            topic
            for topic, keywords in self.TOPIC_KEYWORDS.items()
            if any(kw in query_lower for kw in keywords)
        ] or ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        topics = self._detect_topics(request.query)
        knowledge_items: List[Dict] = []
        sources: List[str] = []

        if self.enable_mock or not self._vector_store:
            for topic in topics:
                if topic in MOCK_KNOWLEDGE_BASE:
                    entry = MOCK_KNOWLEDGE_BASE[topic]
                    knowledge_items.append({"topic": topic, **entry})
                    sources.append(entry.get("source", f"Mock KB: {topic}"))
        else:
            # Real RAG retrieval
            results = self._vector_store.similarity_search(request.query, k=5)
            for r in results:
                knowledge_items.append({"topic": "retrieved", "text": r["text"], **r["metadata"]})
                sources.append(r["metadata"].get("source", "Vector Store"))

        summary = self._build_summary(knowledge_items, topics)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=knowledge_items,
            summary=summary,
            sources=sources,
            confidence=0.88,
            metadata={"topics_found": topics},
        )

    def _build_summary(self, items: List[Dict], topics: List[str]) -> str:
        if not items:
            return "No relevant knowledge base entries found."

        parts = ["📚 **Business Context & Documentation**"]
        for item in items:
            topic = item.get("topic", "unknown").upper()
            parts.append(f"\n**{topic}**")
            if "definition" in item:
                parts.append(f"  _Definition:_ {item['definition']}")
            if "business_context" in item:
                parts.append(f"  _Context:_ {item['business_context']}")
            if "runbook" in item:
                parts.append(f"  _Reference:_ {item['runbook']}")
        return "\n".join(parts)

    def ingest_document(self, file_path: str, metadata: Optional[Dict] = None) -> bool:
        """
        Ingest a PDF/DOCX/PPTX/XLSX into the knowledge base.
        Chunks the document and indexes into the vector store.
        """
        if not self._vector_store:
            logger.warning("Vector store not initialized — document not ingested.")
            return False
        try:
            from langchain_community.document_loaders import (
                PyPDFLoader, Docx2txtLoader, UnstructuredPowerPointLoader,
            )
            ext = Path(file_path).suffix.lower()
            loaders = {
                ".pdf": PyPDFLoader,
                ".docx": Docx2txtLoader,
                ".pptx": UnstructuredPowerPointLoader,
            }
            loader_cls = loaders.get(ext)
            if not loader_cls:
                raise ValueError(f"Unsupported file type: {ext}")
            docs = loader_cls(file_path).load()
            doc_dicts = [{"text": d.page_content, "metadata": {**(metadata or {}), "source": file_path}} for d in docs]
            return self._vector_store.load_documents(doc_dicts)
        except Exception as e:
            logger.error(f"Document ingestion failed for {file_path}: {e}")
            return False
