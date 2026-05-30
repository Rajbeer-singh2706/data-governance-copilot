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
    _agents_ran: List[str]
