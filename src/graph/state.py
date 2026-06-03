"""AgentState TypedDict — single source of truth for graph state."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # Input
    query: str
    thread_id: str
    user_id: str
    time_range: str
    data_products: List[str]

    # Routing
    intent: str
    next_agents: List[str]

    # Accumulated outputs
    agent_results: Annotated[List[Dict], operator.add]
    sources: Annotated[List[str], operator.add]
    anomalies: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]

    # Write actions
    auto_tickets: List[Dict]
    pending_action: Optional[Dict]
    approved: bool

    # Final output
    final_summary: str
    confidence: float

    # Memory
    conversation_history: List[Dict]
    user_preferences: Dict[str, Any]

    # Metadata
    execution_ms: float
    query_id: str

    # Hook fields (Day 13)
    start_time: float
    guardrail_passed: bool
    guardrail_reason: str
    _agents_ran: List[str]


def initial_state(
    query: str = "",
    thread_id: str = "default",
    user_id: str = "anonymous",
    time_range: str = "last_30_days",
    data_products=None,
    approved: bool = False,
    anomalies=None,
    **kwargs,
) -> AgentState:
    """Factory to build a clean AgentState for testing."""
    state: AgentState = {
        "query": query,
        "thread_id": thread_id,
        "user_id": user_id,
        "time_range": time_range,
        "data_products": data_products or [],
        "approved": approved,
        "agent_results": [],
        "sources": [],
        "anomalies": anomalies or [],
        "errors": [],
        "auto_tickets": [],
        "pending_action": None,
        "final_summary": "",
        "confidence": 0.0,
        "conversation_history": [],
        "user_preferences": {},
        "execution_ms": 0.0,
        "query_id": "",
        "start_time": 0.0,
        "guardrail_passed": True,
        "guardrail_reason": "",
        "_agents_ran": [],
    }
    state.update(kwargs)
    return state