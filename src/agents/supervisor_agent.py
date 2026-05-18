
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from agents.knowledge_agent import KnowledgeAgent
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
    Day 8: InformationAgent + KnowledgeAgent.
    Grows each day as we add more agents.
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
        self.enable_mock = enable_mock
        self.information_agent = InformationAgent(
            config=config, enable_mock=enable_mock
        )
        self.knowledge_agent = KnowledgeAgent(
            config=config, enable_mock=enable_mock
        )

    def run(self, query: str,
            time_range: str = "last_month") -> SupervisorResponse:
        """Main entry point — called by the UI."""
        try:
            products = self._detect_products(query)
            request  = AgentRequest(
                query         = query,
                data_products = products,
                time_range    = time_range,
            )

            # Run both agents
            info_result  = self.information_agent.execute(request)
            know_result  = self.knowledge_agent.execute(request)

            # Merge results
            combined_summary = self._merge_summaries(
                info_result, know_result
            )
            all_sources  = info_result.sources + know_result.sources
            confidence   = (
                info_result.confidence + know_result.confidence
            ) / 2

            return SupervisorResponse(
                query       = query,
                summary     = combined_summary,
                data        = info_result.data,
                anomalies   = info_result.data.get("anomalies", []),
                sources     = all_sources,
                agents_used = [
                    info_result.agent_name,
                    know_result.agent_name,
                ],
                confidence  = round(confidence, 2),
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
        """Scan query for product keywords."""
        q        = query.lower()
        products = set()
        for keyword, product in self.PRODUCT_KEYWORDS.items():
            if keyword in q:
                products.add(product)
        return list(products) if products else ["retention"]

    def _merge_summaries(self,
                          info_result,
                          know_result) -> str:
        """Combine summaries from both agents."""
        parts = []
        if info_result.success and info_result.summary:
            parts.append(info_result.summary)
        if know_result.success and know_result.summary:
            parts.append(know_result.summary)
        return "\n\n---\n\n".join(parts) if parts \
               else "No results found."