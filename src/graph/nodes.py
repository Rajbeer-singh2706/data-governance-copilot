import time
from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from agents.knowledge_agent   import KnowledgeAgent
from agents.metadata_agent    import MetadataAgent
from agents.capacity_agent    import CapacityAgent
from agents.rule_agent        import RuleAgent
from config.settings import config
from graph.state import AgentState

# ── Instantiate agents once (module level) ────────────────

_agents = {
    "information": InformationAgent(
        config=config, enable_mock=config.enable_mock
    ),
    "knowledge":   KnowledgeAgent(
        config=config, enable_mock=config.enable_mock
    ),
    "metadata":    MetadataAgent(
        config=config, enable_mock=config.enable_mock
    ),
    "capacity":    CapacityAgent(
        config=config, enable_mock=config.enable_mock
    ),
    "rule":        RuleAgent(
        config=config, enable_mock=config.enable_mock
    ),
}

def _build_request(state: AgentState) -> AgentRequest:
    """Build AgentRequest from current state."""
    return AgentRequest(
        query         = state["query"],
        intent        = state.get("intent", ""),
        query_id      = state.get("query_id", ""),
        data_products = state.get("data_products", []),
        time_range    = state.get("time_range","last_month"),
    )

# ── Supervisor node ────────────────────────────────────────
from graph.intent import classify_intent, extract_products
from graph.routing import INTENT_AGENT_MAP

def supervisor_node(state: AgentState) -> dict:
    """
    Classifies intent, extracts products,
    decides which agents to run.
    Today: keyword-based (Day 13 upgrades to GPT-4o).
    """
    query    = state["query"]
    intent   = classify_intent(query)
    products = (state.get("data_products") or
                extract_products(query))
    agents   = INTENT_AGENT_MAP.get(intent, [
        "information","knowledge"
    ])

    return {
        "intent":        intent,
        "next_agents":   agents,
        "data_products": products,
    }

# ── Agent nodes — one per agent ────────────────────────────
def information_node(state: AgentState) -> dict:
    result = _agents["information"].execute(
        _build_request(state)
    )
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
        "anomalies":     result.data.get("anomalies",[])
                         if result.success else [],
    }

def knowledge_node(state: AgentState) -> dict:
    result = _agents["knowledge"].execute(
        _build_request(state)
    )
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }

def metadata_node(state: AgentState) -> dict:
    result = _agents["metadata"].execute(
        _build_request(state)
    )
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }

def capacity_node(state: AgentState) -> dict:
    result = _agents["capacity"].execute(
        _build_request(state)
    )
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }

def rule_node(state: AgentState) -> dict:
    result = _agents["rule"].execute(
        _build_request(state)
    )
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }

# ── Auto-ticket node ───────────────────────────────────────
def auto_ticket_node(state: AgentState) -> dict:
    """Create Jira tickets for critical anomalies."""
    anomalies = state.get("anomalies", [])
    products  = state.get("data_products", ["unknown"])
    created   = []

    capacity = _agents["capacity"]
    for anomaly in anomalies:
        if any(kw in anomaly.lower()
               for kw in ["threshold","missing",
                           "below","risk"]):
            result = capacity.create_ticket_from_anomaly(
                anomaly, products[0]
            )
            if result.success:
                created.append(
                    result.data.get("ticket_id","?")
                )

    return {"auto_tickets": created}

# ── Synthesizer node ───────────────────────────────────────
def synthesizer_node(state: AgentState) -> dict:
    """
    Merge all agent summaries into one response.
    Day 13 upgrades this to GPT-4o synthesis.
    """
    results = state.get("agent_results", [])
    parts   = [
        r.get("summary","")
        for r in results
        if r.get("success") and r.get("summary")
    ]
    summary = "\n\n---\n\n".join(parts) \
              if parts else "No results found."

    scores     = [r.get("confidence",0) for r in results
                  if r.get("success")]
    confidence = round(sum(scores)/len(scores), 2) \
                 if scores else 0.0

    # Add to conversation history (memory)
    history_entry = {
        "query":   state["query"],
        "summary": summary[:500],
        "intent":  state.get("intent",""),
        "tickets": state.get("auto_tickets",[]),
    }

    return {
        "final_summary":        summary,
        "confidence":           confidence,
        "conversation_history": [history_entry],
    }