"""Supervisor Agent — legacy orchestrator (kept for compatibility)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.base_agent import AgentRequest, AgentResult, BaseAgent


@dataclass
class SupervisorResponse:
    success: bool
    summary: str = ""
    agents_used: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


class SupervisorAgent(BaseAgent):
    """Legacy orchestrator — LangGraph nodes supersede this in production."""

    _RULE_KEYWORDS = ["rule", "governance policy", "define", "create rule", "list rule"]
    _RULE_ONLY_KEYWORDS = ["list all rules", "list rules", "show rules"]

    def execute(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            success=True,
            message="Use LangGraph graph.invoke() instead of SupervisorAgent directly.",
            confidence=1.0,
        )

    def run(self, query: str) -> SupervisorResponse:
        """Legacy run() interface dispatching to agents based on query."""
        q = query.lower()

        if any(kw in q for kw in self._RULE_KEYWORDS):
            from agents.rule_agent import RuleAgent
            agent = RuleAgent()
            req = AgentRequest(query=query)
            result = agent.execute(req)
            return SupervisorResponse(
                success=result.success,
                summary=result.message,
                agents_used=["rule_agent"],
                data={"rules": result.data},
                confidence=result.confidence,
            )

        # Default: information agent
        from agents.information_agent import InformationAgent
        agent = InformationAgent()
        req = AgentRequest(query=query)
        result = agent.execute(req)
        return SupervisorResponse(
            success=result.success,
            summary=result.message,
            agents_used=["information_agent"],
            data=result.data or {},
            confidence=result.confidence,
        )
