import operator
from typing import  Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):

    # ── Input ────────────────────────────────────
    query:          str
    thread_id:      str
    user_id:        str
    time_range:     str
    data_products:  List[str]

    # ── Routing (set by supervisor node) ─────────
    intent:         str
    next_agents:    List[str]

    # ── Agent outputs (accumulated via operator.add)
    agent_results:  Annotated[List[dict], operator.add]
    sources:        Annotated[List[str],  operator.add]
    anomalies:      Annotated[List[str],  operator.add]
    errors:         Annotated[List[dict], operator.add]

    # ── Write actions ────────────────────────────
    auto_tickets:   List[str]
    pending_action: Optional[dict]
    approved:       bool

    # ── Final output ─────────────────────────────
    final_summary:  str
    confidence:     float

    # ── Memory ───────────────────────────────────
    conversation_history: Annotated[List[dict], operator.add]
    user_preferences:     dict

    # ── Execution metadata ───────────────────────
    execution_ms:   float
    query_id:       str


def initial_state(
    query: str,
    thread_id: str  = "default",
    user_id:   str  = "anonymous",
    time_range: str = "last_month",
) -> dict:
    """Build clean initial state for a new query."""
    import uuid
    return {
        "query":               query,
        "thread_id":           thread_id,
        "user_id":             user_id,
        "time_range":          time_range,
        "data_products":       [],
        "intent":              "",
        "next_agents":         [],
        "agent_results":       [],
        "sources":             [],
        "anomalies":           [],
        "errors":              [],
        "auto_tickets":        [],
        "pending_action":      None,
        "approved":            False,
        "final_summary":       "",
        "confidence":          0.0,
        "conversation_history":[],
        "user_preferences":    {},
        "execution_ms":        0.0,
        "query_id":            str(uuid.uuid4())[:8],
    }