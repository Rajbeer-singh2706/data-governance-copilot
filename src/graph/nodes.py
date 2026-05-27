"""
src/graph/nodes.py
All LangGraph node functions.

Agent singletons are initialized at import time.
If a required service (Databricks, Jira, Collibra, pgvector) is not
configured, the agent raises EnvironmentError at construction time —
this is caught here and results in AgentResult(success=False) for
every call to that agent, surfaced clearly to the user.
"""
from __future__ import annotations

import os
import time

from core.base_agent import AgentRequest, AgentResult
from core.cache import cached_node
from core.retry import retry_agent_call

from agents.information_agent import InformationAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.metadata_agent import MetadataAgent
from agents.capacity_agent import CapacityAgent
from agents.rule_agent import RuleAgent
from config.settings import config
from graph.state import AgentState


# ── Agent singletons — fail loudly at startup if config is missing ────────

def _try_init(cls, **kwargs):
    """Attempt to construct an agent; return a stub on EnvironmentError."""
    try:
        return cls(**kwargs)
    except EnvironmentError as exc:
        import logging
        logging.getLogger("nodes").warning(
            "[nodes] %s not initialized: %s", cls.__name__, exc
        )
        return _UnconfiguredAgent(cls.name if hasattr(cls, "name") else cls.__name__, str(exc))


class _UnconfiguredAgent:
    """Stands in for an agent whose credentials are not configured."""
    def __init__(self, name: str, reason: str):
        self._name = name
        self._reason = reason

    def execute(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_name=self._name,
            success=False,
            error=self._reason,
            summary=(
                f"⚠️ **{self._name}** is not configured.\n"
                f"  Reason: {self._reason}\n"
                f"  Set the required environment variables and restart."
            ),
        )


_agents = {
    "information": _try_init(InformationAgent, config=config),
    "knowledge":   _try_init(KnowledgeAgent,   config=config),
    "metadata":    _try_init(MetadataAgent,     config=config),
    "capacity":    _try_init(CapacityAgent,     config=config),
    "rule":        RuleAgent(config=config),   # always succeeds — no external deps
}


def _build_request(state: AgentState) -> AgentRequest:
    return AgentRequest(
        query=state["query"],
        intent=state.get("intent", ""),
        query_id=state.get("query_id", ""),
        data_products=state.get("data_products", []),
        time_range=state.get("time_range", "last_month"),
    )


# ══════════════════════════════════════════════════════════════════════════
# pre_hook_node
# ══════════════════════════════════════════════════════════════════════════
def pre_hook_node(state: AgentState) -> dict:
    """Guardrails + PII redaction + start_time recording."""
    from core.guardrails import run_guardrails

    raw_query = state.get("query", "").strip()
    t_start = time.time()
    result = run_guardrails(raw_query)

    if not result.passed:
        print(f"[pre_hook] BLOCKED — {result.reason}")
        return {
            "guardrail_passed": False,
            "final_summary":    f"⚠️ Request blocked: {result.reason}",
            "confidence":       0.0,
            "errors":           [{"node": "pre_hook", "reason": result.reason}],
            "start_time":       t_start,
        }

    if result.pii_found:
        print("[pre_hook] PII detected and redacted.")

    print(f"[pre_hook] OK | checks={result.checks_run} | pii={result.pii_found}")
    return {
        "query":            result.cleaned_query,
        "guardrail_passed": True,
        "start_time":       t_start,
    }


# ══════════════════════════════════════════════════════════════════════════
# supervisor_node
# ══════════════════════════════════════════════════════════════════════════
from graph.intent import classify_intent_gpt
from graph.routing import INTENT_AGENT_MAP


def supervisor_node(state: AgentState) -> dict:
    """Groq/GPT-4o intent classification + agent routing."""
    classification = classify_intent_gpt(state["query"])
    intent = classification.intent.value
    products = state.get("data_products") or classification.data_products or []
    agents = INTENT_AGENT_MAP.get(intent, ["information", "knowledge"])

    print(
        f"[supervisor] intent={intent} | conf={classification.confidence:.2f} | "
        f"products={products} | agents={agents}\n"
        f"  reasoning: {classification.reasoning}"
    )
    return {
        "intent":        intent,
        "next_agents":   agents,
        "data_products": products,
        "confidence":    classification.confidence,
    }


# ══════════════════════════════════════════════════════════════════════════
# Cached agent nodes
# ══════════════════════════════════════════════════════════════════════════

@cached_node("information_agent", ttl=1800)
def information_node(state: AgentState) -> dict:
    result = retry_agent_call(
        _agents["information"].execute,
        _build_request(state),
        max_retries=3,
    )
    data = (result.data or {}) if result.success else {}
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources if result.success else [],
        "anomalies":     data.get("anomalies", []),
        "errors":        [] if result.success else [
            {"node": "information_node", "error": result.error}
        ],
    }


@cached_node("knowledge_agent", ttl=7200)
def knowledge_node(state: AgentState) -> dict:
    result = retry_agent_call(
        _agents["knowledge"].execute,
        _build_request(state),
        max_retries=3,
    )
    data = (result.data or {}) if result.success else {}
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources if result.success else [],
        "anomalies":     data.get("anomalies", []),
        "errors":        [] if result.success else [
            {"node": "knowledge_node", "error": result.error}
        ],
    }


@cached_node("metadata_agent", ttl=3600)
def metadata_node(state: AgentState) -> dict:
    result = retry_agent_call(
        _agents["metadata"].execute,
        _build_request(state),
        max_retries=3,
    )
    data = (result.data or {}) if result.success else {}
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources if result.success else [],
        "anomalies":     data.get("anomalies", []),
        "errors":        [] if result.success else [
            {"node": "metadata_node", "error": result.error}
        ],
    }


def capacity_node(state: AgentState) -> dict:
    result = _agents["capacity"].execute(_build_request(state))
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }


def rule_node(state: AgentState) -> dict:
    result = _agents["rule"].execute(_build_request(state))
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }


# ══════════════════════════════════════════════════════════════════════════
# auto_ticket_node
# ══════════════════════════════════════════════════════════════════════════

def auto_ticket_node(state: AgentState) -> dict:
    anomalies = state.get("anomalies", [])
    approved = state.get("approved", False)
    products = state.get("data_products", ["unknown"])

    critical = [a for a in anomalies if any(
        kw in a.lower() for kw in
        ["threshold", "missing", "below", "risk", "drop", "fail"]
    )]

    if not critical:
        return {"auto_tickets": [], "pending_action": None}

    if not approved:
        return {
            "pending_action": {
                "action":    "create_jira_tickets",
                "anomalies": critical,
                "products":  products,
                "count":     len(critical),
                "message":   (
                    f"Found {len(critical)} critical anomaly/anomalies in "
                    f"{', '.join(products)}. Approve Jira ticket creation?"
                ),
            },
            "auto_tickets": [],
        }

    created = []
    capacity = _agents["capacity"]
    if not hasattr(capacity, "create_ticket_from_anomaly"):
        return {
            "auto_tickets": [],
            "pending_action": {
                "action":  "create_jira_tickets",
                "error":   "CapacityAgent not configured — set JIRA_* env vars.",
                "anomalies": critical,
            },
        }
    for anomaly in critical:
        result = capacity.create_ticket_from_anomaly(anomaly, products[0])
        if result.success:
            created.append(result.data.get("ticket_id", "?"))

    return {"auto_tickets": created, "pending_action": None, "approved": True}


# ══════════════════════════════════════════════════════════════════════════
# synthesizer_node
# ══════════════════════════════════════════════════════════════════════════

_SYNTH_SYSTEM = """\
You are the final synthesis layer of an enterprise Data Governance AI Copilot.
Combine results from multiple specialist agents into one clear, executive-quality
answer for a business analyst.

Guidelines:
  • Answer the user's question directly in the first paragraph.
  • Use ONLY the agent results provided — never hallucinate facts or numbers.
  • Use markdown: **bold** for key metrics, bullet points for lists.
  • Flag anomalies with ⚠️ and auto-created tickets with 🎫.
  • End with "**Next steps:**" only when obvious follow-up exists.
  • Target: 120–300 words. Be concise.
  • If no agents returned results, say so honestly.
"""

_SYNTH_HUMAN = """\
Original query:           {query}
Detected intent:          {intent}
Data products in scope:   {products}
Auto-created tickets:     {tickets}

Agent results:
{agent_context}

Write a clear, accurate answer to the original query.
"""

_synth_llm = None


def _get_synth_llm():
    global _synth_llm
    if _synth_llm is None:
        from core.llm_factory import get_llm
        _synth_llm = get_llm(config.llm, streaming=False)
    return _synth_llm


def synthesizer_node(state: AgentState) -> dict:
    """Synthesis via LiteLLM (Groq primary). Falls back to string-join."""
    from langchain_core.messages import SystemMessage, HumanMessage

    results = state.get("agent_results", [])
    query = state["query"]
    intent = state.get("intent", "unknown")
    products = state.get("data_products", [])
    tickets = state.get("auto_tickets", [])

    successful = [r for r in results if r.get("success") and r.get("summary")]
    agent_context = "\n\n".join(
        f"### {r['agent']}\n{r['summary']}" for r in successful
    ) if successful else "No agents returned successful results."

    sup_conf = state.get("confidence", 0.0)
    scores = [r.get("confidence", 0.0) for r in results if r.get("success")]
    all_scores = ([sup_conf] if sup_conf else []) + scores
    avg_conf = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    if not os.getenv("GROQ_API_KEY", "") or not successful:
        parts = [r.get("summary", "") for r in successful]
        summary = "\n\n---\n\n".join(parts) if parts else "No results found."
    else:
        try:
            llm = _get_synth_llm()
            msgs = [
                SystemMessage(content=_SYNTH_SYSTEM),
                HumanMessage(content=_SYNTH_HUMAN.format(
                    query=query,
                    intent=intent,
                    products=", ".join(products) or "not specified",
                    tickets=", ".join(tickets) if tickets else "none",
                    agent_context=agent_context,
                )),
            ]
            summary = llm.invoke(msgs).content.strip()
        except Exception as exc:
            print(f"[synthesizer] LiteLLM failed — string fallback. Error: {exc}")
            parts = [r.get("summary", "") for r in successful]
            summary = "\n\n---\n\n".join(parts) if parts else "No results found."

    history_entry = {
        "query":   query,
        "summary": summary[:500],
        "intent":  intent,
        "tickets": tickets,
    }
    return {
        "final_summary":        summary,
        "confidence":           avg_conf,
        "conversation_history": [history_entry],
    }


# ══════════════════════════════════════════════════════════════════════════
# post_hook_node
# ══════════════════════════════════════════════════════════════════════════

def post_hook_node(state: AgentState) -> dict:
    """Compute execution_ms and emit structured audit log."""
    t_end = time.time()
    t_start = state.get("start_time", t_end)
    elapsed_ms = round((t_end - t_start) * 1000, 1)

    agents_used = [r.get("agent", "?") for r in state.get("agent_results", [])
                   if r.get("agent")]

    print(
        f"[post_hook] query_id={state.get('query_id')} | "
        f"intent={state.get('intent', 'n/a')} | "
        f"guardrail_passed={state.get('guardrail_passed', True)} | "
        f"agents={agents_used} | "
        f"confidence={state.get('confidence', 0.0):.2f} | "
        f"execution_ms={elapsed_ms}"
    )
    return {"execution_ms": elapsed_ms}
