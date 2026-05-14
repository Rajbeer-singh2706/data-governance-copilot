from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from config.settings import config

@dataclass
class SupervisorResponse:
    """What the supervisor returns to the UI."""
    query:        str
    summary:      str
    data:         Dict[str, Any] = field(default_factory=dict)
    anomalies:    List[str]      = field(default_factory=list)
    sources:      List[str]      = field(default_factory=list)
    agents_used:  List[str]      = field(default_factory=list)
    confidence:   float          = 0.0
    success:      bool           = True
    error:        Optional[str]  = None
    timestamp:    str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class SupervisorAgent:
    """
    Minimal supervisor for Day 7.
    Routes queries to InformationAgent.
    Grows each day as we add more agents.
    """

    # keyword → data product mapping
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
        # agents registered so far — grows each day
        self.information_agent = InformationAgent(
            config=config,
            enable_mock=enable_mock
        )

    def run(self, query: str,
            time_range: Optional[str] = None) -> SupervisorResponse:
        """Main entry point — called by the UI."""
        try:
            # Step 1: detect products from query
            products = self._detect_products(query)

            # Step 2: build agent request
            request = AgentRequest(
                query         = query,
                data_products = products,
                time_range    = time_range or "last_month",
            )

            # Step 3: run information agent
            result = self.information_agent.execute(request)

            # Step 4: build and return response
            return SupervisorResponse(
                query       = query,
                summary     = result.summary,
                data        = result.data,
                anomalies   = result.data.get("anomalies", []),
                sources     = result.sources,
                agents_used = [result.agent_name],
                confidence  = result.confidence,
                success     = result.success,
                error       = result.error,
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