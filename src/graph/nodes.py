"""All LangGraph nodes."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.base_agent import AgentRequest
from core.cache import cached_node
from core.guardrails import check_guardrails
from core.retry import retry_agent_call
from graph.state import AgentState

_HITL_KEYWORDS = ["threshold", "missing", "below", "risk", "drop", "fail"]


def pre_hook(state: AgentState) -> AgentState:
    """Validate input, run guardrails, record start time."""
    import logging
    logger = logging.getLogger("graph.pre_hook")
    result = check_guardrails(state.get("query", ""))
    if not result.passed:
        logger.warning(f"Guardrail blocked query reason={result.reason!r} query={state.get('query', '')!r}")
    return {
        **state,
        "query": result.query,
        "guardrail_passed": result.passed,
        "guardrail_reason": result.reason,
        "final_summary": f"🚫 Blocked: {result.reason}" if not result.passed else "",
        "start_time": time.perf_counter(),
        "query_id": str(uuid.uuid4())[:8],
        "agent_results": [],
        "sources": [],
        "anomalies": [],
        "errors": [],
        "auto_tickets": [],
    }


def post_hook(state: AgentState) -> AgentState:
    """Record execution time and audit log."""
    start = state.get("start_time", time.perf_counter())
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {**state, "execution_ms": round(elapsed_ms, 2)}


def supervisor_node(state: AgentState) -> AgentState:
    """Classify intent and determine which agents to run."""
    from graph.intent import classify_intent
    from graph.routing import get_agents_for_intent

    classification = classify_intent(state.get("query", ""))
    return {
        **state,
        "intent": classification.intent.value,
        "next_agents": get_agents_for_intent(classification.intent.value),
        "data_products": classification.data_products or state.get("data_products", []),
    }


@cached_node("information_agent", ttl=1800)
def information_node(state: AgentState) -> AgentState:
    agent = _get_agent("information")
    request = AgentRequest(
        query=state.get("query", ""),
        time_range=state.get("time_range", "last_30_days"),
        data_products=state.get("data_products", []),
        thread_id=state.get("thread_id", "default"),
    )
    result = retry_agent_call(agent.execute, request)
    anomalies = (result.data or {}).get("anomalies", []) if result.success else []
    return {
        **state,
        "agent_results": [{"agent": "information", "data": result.data, "success": result.success}],
        "sources": result.sources,
        "anomalies": anomalies,
        "errors": result.errors,
    }


@cached_node("knowledge_agent", ttl=7200)
def knowledge_node(state: AgentState) -> AgentState:
    agent = _get_agent("knowledge")
    request = AgentRequest(
        query=state.get("query", ""),
        thread_id=state.get("thread_id", "default"),
        data_products=state.get("data_products", []),
    )
    result = retry_agent_call(agent.execute, request)
    return {
        **state,
        "agent_results": [{"agent": "knowledge", "data": result.data, "success": result.success}],
        "sources": result.sources,
        "errors": result.errors,
    }


@cached_node("metadata_agent", ttl=3600)
def metadata_node(state: AgentState) -> AgentState:
    agent = _get_agent("metadata")
    request = AgentRequest(
        query=state.get("query", ""),
        thread_id=state.get("thread_id", "default"),
        data_products=state.get("data_products", []),
    )
    result = retry_agent_call(agent.execute, request)
    return {
        **state,
        "agent_results": [{"agent": "metadata", "data": result.data, "success": result.success}],
        "sources": result.sources,
        "errors": result.errors,
    }


def capacity_node(state: AgentState) -> AgentState:
    from agents.capacity_agent import CapacityAgent
    agent = CapacityAgent()
    request = AgentRequest(
        query=state.get("query", ""),
        thread_id=state.get("thread_id", "default"),
        data_products=state.get("data_products", []),
    )
    result = agent.execute(request)
    return {
        **state,
        "agent_results": [{"agent": "capacity", "data": result.data, "success": result.success}],
        "sources": result.sources,
        "errors": result.errors,
    }


def rule_node(state: AgentState) -> AgentState:
    from agents.rule_agent import RuleAgent
    agent = RuleAgent()
    request = AgentRequest(
        query=state.get("query", ""),
        data_products=state.get("data_products", []),
    )
    result = agent.execute(request)
    return {
        **state,
        "agent_results": [{"agent": "rule", "data": result.data, "success": result.success}],
        "errors": result.errors,
    }


def auto_ticket_node(state: AgentState) -> AgentState:
    """HITL gate — create tickets only after explicit approval."""
    anomalies = state.get("anomalies", [])
    approved = state.get("approved", False)

    if not anomalies:
        return state

    # First pass: set pending_action, wait for approval
    if not approved:
        hitl_keywords = _HITL_KEYWORDS
        if any(any(kw in a.lower() for kw in hitl_keywords) for a in anomalies):
            products = list({p for a in anomalies for p in ["retention","bookings","cac","ltv"] if p in a.lower()})
            return {
                **state,
                "pending_action": {
                    "action": "create_jira_tickets",
                    "type": "create_tickets",
                    "anomalies": anomalies,
                    "count": len(anomalies),
                    "products": products,
                    "message": f"Create {len(anomalies)} Jira ticket(s) for detected anomalies?",
                    "description": f"Create {len(anomalies)} Jira ticket(s) for detected anomalies?",
                },
            }
        return state

    # Second pass: approved — create tickets
    from agents.capacity_agent import CapacityAgent
    agent = CapacityAgent()

    if not hasattr(agent, "create_ticket_from_anomaly"):
        return {
            **state,
            "pending_action": {"error": "CapacityAgent does not support ticket creation"},
            "approved": False,
        }

    tickets = []
    for anomaly in anomalies:
        product = "general"
        for p in ["retention", "bookings", "cac", "ltv"]:
            if p in anomaly.lower():
                product = p
                break
        result = agent.create_ticket_from_anomaly(anomaly, product=product)
        if result.success:
            tickets.append(result.data.get("ticket", {}))

    return {
        **state,
        "auto_tickets": tickets,
        "pending_action": None,
        "approved": False,
    }


def synthesizer_node(state: AgentState) -> AgentState:
    """Synthesize agent results into a final summary using LLM."""
    agent_results = state.get("agent_results", [])
    anomalies = state.get("anomalies", [])
    query = state.get("query", "")

    # Build context from agent results
    context_parts = []
    for r in agent_results:
        agent_name = r.get("agent", "unknown")
        data = r.get("data") or {}
        if data:
            context_parts.append(f"[{agent_name}]: {str(data)[:500]}")

    context = "\n".join(context_parts) if context_parts else "No agent data available."
    anomaly_str = "; ".join(anomalies) if anomalies else "None"

    try:
        from core.llm_factory import get_llm
        llm = get_llm()
        prompt = (
            f"You are a Data Governance Copilot. Answer the following question concisely "
            f"based on the data below.\n\n"
            f"Question: {query}\n\n"
            f"Agent Data:\n{context}\n\n"
            f"Anomalies Detected: {anomaly_str}\n\n"
            f"Provide a clear, actionable summary in 2-3 sentences."
        )
        response = llm.invoke(prompt)
        summary = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        import logging
        logging.getLogger("graph.synthesizer").error(
            f"LLM synthesis failed, using string fallback: {exc}", exc_info=True
        )
        # String fallback
        summary = (
            f"Analysis complete for: '{query}'. "
            f"{'Anomalies detected: ' + anomaly_str + '.' if anomalies else 'No anomalies detected.'} "
            f"Agents consulted: {', '.join(r.get('agent', '') for r in agent_results)}."
        )

    scores = [r.get("confidence", 0.8) for r in agent_results if r.get("confidence")]
    avg_confidence = round(sum(scores) / len(scores), 3) if scores else 0.8

    return {**state, "final_summary": summary, "confidence": avg_confidence}

# Agent registry — accessible for testing/patching
def _build_agents() -> dict:
    from agents.information_agent import InformationAgent
    from agents.knowledge_agent import KnowledgeAgent
    from agents.metadata_agent import MetadataAgent
    from agents.capacity_agent import CapacityAgent
    from agents.rule_agent import RuleAgent
    return {
        "information": InformationAgent(),
        "knowledge": KnowledgeAgent(),
        "metadata": MetadataAgent(),
        "capacity": CapacityAgent(),
        "rule": RuleAgent(),
    }

_agents: dict = {}

def _get_agent(name: str):
    if not _agents:
        _agents.update(_build_agents())
    return _agents.get(name)

# Eagerly populate at import time (tests access _agents["information"] before invoke)
try:
    _agents.update(_build_agents())
except Exception:
    pass  # Will populate lazily on first call