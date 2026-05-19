# src/agents/supervisor_agent.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from agents.knowledge_agent   import KnowledgeAgent
from agents.metadata_agent    import MetadataAgent
from agents.capacity_agent    import CapacityAgent
from agents.rule_agent import RuleAgent
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
    auto_tickets: List[str]      = field(default_factory=list)
    confidence:   float          = 0.0
    success:      bool           = True
    error:        Optional[str]  = None
    timestamp:    str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class SupervisorAgent:
    """
    Routes queries to all registered agents and merges results.
    Day 10: Information + Knowledge + Metadata + Capacity.
    Also auto-creates Jira tickets for detected anomalies.
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
        self.enable_mock       = enable_mock
        self.information_agent = InformationAgent(
            config=config, enable_mock=enable_mock
        )
        self.knowledge_agent   = KnowledgeAgent(
            config=config, enable_mock=enable_mock
        )
        self.metadata_agent    = MetadataAgent(
            config=config, enable_mock=enable_mock
        )
        self.capacity_agent    = CapacityAgent(
            config=config, enable_mock=enable_mock
        )
        self.rule_agent = RuleAgent(
            config=config, enable_mock=enable_mock
        )

    def run(self, query: str,
            time_range: str = "last_month") -> SupervisorResponse:
        try:
            # Rule queries get their own fast path
            if self._is_rule_query(query):
                return self._run_rule_query(query)
            
            products = self._detect_products(query)
            request  = AgentRequest(
                query         = query,
                data_products = products,
                time_range    = time_range,
            )

            # Run all four agents
            info_result     = self.information_agent.execute(request)
            know_result     = self.knowledge_agent.execute(request)
            meta_result     = self.metadata_agent.execute(request)
            capacity_result = self.capacity_agent.execute(request)

            # Auto-create tickets from anomalies
            anomalies    = info_result.data.get("anomalies", [])
            auto_tickets = self._auto_create_tickets(
                anomalies, products
            )

            # Merge all results
            combined    = self._merge_summaries(
                info_result, know_result,
                meta_result, capacity_result
            )
            all_sources = (
                info_result.sources
                + know_result.sources
                + meta_result.sources
                + capacity_result.sources
            )
            confidence = round((
                info_result.confidence
                + know_result.confidence
                + meta_result.confidence
                + capacity_result.confidence
            ) / 4, 2)

            return SupervisorResponse(
                query        = query,
                summary      = combined,
                data         = info_result.data,
                anomalies    = anomalies,
                sources      = all_sources,
                agents_used  = [
                    info_result.agent_name,
                    know_result.agent_name,
                    meta_result.agent_name,
                    capacity_result.agent_name,
                ],
                auto_tickets = auto_tickets,
                confidence   = confidence,
                success      = info_result.success,
                error        = info_result.error,
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

    def _auto_create_tickets(self, anomalies: List[str],
                              products: List[str]) -> List[str]:
        """Auto-create Jira ticket for each critical anomaly."""
        created = []
        for anomaly in anomalies:
            if any(
                kw in anomaly.lower()
                for kw in ["threshold", "missing",
                           "below", "risk"]
            ):
                product = products[0] if products else "unknown"
                result  = self.capacity_agent\
                              .create_ticket_from_anomaly(
                                  anomaly, product
                              )
                if result.success:
                    ticket_id = result.data.get(
                        "ticket_id", "?"
                    )
                    created.append(ticket_id)
        return created

    def _merge_summaries(self, *results) -> str:
        parts = [
            r.summary
            for r in results
            if r.success and r.summary
        ]
        return "\n\n---\n\n".join(parts) if parts \
               else "No results found."

    # 4. Add the two new helper methods:
    def _is_rule_query(self, query: str) -> bool:
        """Check if query is about rules."""
        q = query.lower()
        return any(kw in q for kw in [
            "create rule", "add rule", "define rule",
            "new rule",    "list rules","show rules",
            "all rules",   "evaluate",  "check rules",
            "run rules",   "validate",  "create dq rule",
        ])

    def _run_rule_query(self,
                        query: str) -> SupervisorResponse:
        """Fast path — only rule agent runs."""
        request = AgentRequest(query=query)
        result  = self.rule_agent.execute(request)

        return SupervisorResponse(
            query       = query,
            summary     = result.summary,
            data        = {"rules": result.data},
            sources     = result.sources,
            agents_used = [result.agent_name],
            confidence  = result.confidence if result.success
                        else 0.0,
            success     = result.success,
            error       = result.error,
        )