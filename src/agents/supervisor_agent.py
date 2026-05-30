"""Supervisor Agent — legacy orchestrator (kept for compatibility)."""
from __future__ import annotations

import pytest

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent


class SupervisorAgent(BaseAgent):
    """Legacy orchestrator — LangGraph nodes supersede this in production."""

    def execute(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            success=True,
            message="Use LangGraph graph.invoke() instead of SupervisorAgent directly.",
            confidence=1.0,
        )
