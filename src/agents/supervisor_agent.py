from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from agents.knowledge_agent   import KnowledgeAgent
from agents.metadata_agent    import MetadataAgent
from config.settings import config


@dataclass
class SupervisorResponse:
    """What the supervisor returns to the UI."""
    query:       str
    summary:     str
    data:        Dict[str, Any] = field(default_factory=dict)
    anomalies:   List[str]      = field(default_factory=list)
    sources:     List[str]      = field(default_factory=list)
    agents_used: List[str]      = field(default_factory=list)
    confidence:  float          = 0.0
    success:     bool           = True
    error:       Optional[str]  = None
    timestamp:   str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class SupervisorAgent:
    """
    Routes queries to registered agents and merges results.
    Day 9: InformationAgent + KnowledgeAgent + MetadataAgent.
    """

    PRODUCT_KEYWORDS = {
        "retention": "retention",  "churn":    "retention",
        "grr":       "retention",  "nrr":      "retention",
        "bookings":  "bookings",   "revenue":  "bookings",
        "arr":       "bookings",   "mrr":      "bookings",
        "cac":       "cac",        "payback":  "cac",
        "ltv":       "ltv",        "lifetime": "ltv",
    }

    def __init__(self, enable_mock: bool = True):
        self.enable_mock        = enable_mock
        self.information_agent  = InformationAgent(
            config=config, enable_mock=enable_mock
        )
        self.knowledge_agent    = KnowledgeAgent(
            config=config, enable_mock=enable_mock
        )
        self.metadata_agent     = MetadataAgent(
            config=config, enable_mock=enable_mock
        )

    def run(self, query: str,
            time_range: str = "last_month") -> SupervisorResponse:
        try:
            products = self._detect_products(query)
            request  = AgentRequest(
                query         = query,
                data_products = products,
                time_range    = time_range,
            )

            # Run all three agents
            info_result  = self.information_agent.execute(request)
            know_result  = self.knowledge_agent.execute(request)
            meta_result  = self.metadata_agent.execute(request)

            # Merge everything
            combined = self._merge_summaries(
                info_result, know_result, meta_result
            )
            all_sources = (
                info_result.sources
                + know_result.sources
                + meta_result.sources
            )
            confidence = round((
                info_result.confidence
                + know_result.confidence
                + meta_result.confidence
            ) / 3, 2)

            return SupervisorResponse(
                query       = query,
                summary     = combined,
                data        = info_result.data,
                anomalies   = info_result.data.get("anomalies", []),
                sources     = all_sources,
                agents_used = [
                    info_result.agent_name,
                    know_result.agent_name,
                    meta_result.agent_name,
                ],
                confidence  = confidence,
                success     = info_result.success,
                error       = info_result.error,
            )

        except Exception as e:
            return SupervisorResponse(
                query   = query,
                summary = f"Something went wrong: {str(e)}",
                success = False,
                error   = str(e),
            )

    def _detect_products(self, query: str) -> List[str]:
        q        = query.lower()
        products = set()
        for keyword, product in self.PRODUCT_KEYWORDS.items():
            if keyword in q:
                products.add(product)
        return list(products) if products else ["retention"]

    def _merge_summaries(self, *results) -> str:
        """Merge any number of agent results into one summary."""
        parts = [
            r.summary
            for r in results
            if r.success and r.summary
        ]
        return "\n\n---\n\n".join(parts) if parts \
               else "No results found."