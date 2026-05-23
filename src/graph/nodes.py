"""
src/graph/nodes.py
Day 13 upgrades:
  • pre_hook_node     — guardrails + query normalisation + start timer (NEW)
  • supervisor_node   — GPT-4o IntentClassification (replaces keyword classifier)
  • synthesizer_node  — GPT-4o narrative synthesis (replaces string join)
  • post_hook_node    — execution timing + audit log (NEW)
 
All other agent nodes (information, knowledge, metadata, capacity, rule,
auto_ticket) are unchanged from Day 12.
 
LangSmith traces every LLM call automatically via env vars:
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=<your key>
  LANGCHAIN_PROJECT=data-governance-copilot
"""
from __future__ import annotations
 
import os
import time


from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent
from agents.knowledge_agent   import KnowledgeAgent
from agents.metadata_agent    import MetadataAgent
from agents.capacity_agent    import CapacityAgent
from agents.rule_agent        import RuleAgent
from config.settings          import config
from graph.state              import AgentState
 
 
# ── Agent singletons (instantiated once at module load) ───────────────────
 
_agents = {
    "information": InformationAgent(config=config, enable_mock=config.enable_mock),
    "knowledge":   KnowledgeAgent(  config=config, enable_mock=config.enable_mock),
    "metadata":    MetadataAgent(   config=config, enable_mock=config.enable_mock),
    "capacity":    CapacityAgent(   config=config, enable_mock=config.enable_mock),
    "rule":        RuleAgent(       config=config, enable_mock=config.enable_mock),
}
 
 
def _build_request(state: AgentState) -> AgentRequest:
    """Assemble an AgentRequest from the current graph state."""
    return AgentRequest(
        query         = state["query"],
        intent        = state.get("intent", ""),
        query_id      = state.get("query_id", ""),
        data_products = state.get("data_products", []),
        time_range    = state.get("time_range", "last_month"),
    )
 
 
# ══════════════════════════════════════════════════════════════════════════
# DAY 13 — NEW NODE: pre_hook_node
# Runs first on every query.  Responsibilities:
#   1. Run guardrails (length, SQL injection, prompt injection, PII)
#   2. Normalise / clean the query (PII redaction)
#   3. Record start_time so post_hook can compute execution_ms
# ══════════════════════════════════════════════════════════════════════════
 
def pre_hook_node(state: AgentState) -> dict:
    """
    Guardrails + normalisation + timer start.
 
    If guardrails FAIL:
      • Sets guardrail_passed = False
      • Sets final_summary    = human-readable rejection message
      • route_after_pre_hook() will jump straight to post_hook → END
 
    If guardrails PASS:
      • Forwards cleaned_query (PII stripped) as the new query
      • Sets start_time for execution_ms calculation in post_hook
    """
    from core.guardrails import run_guardrails
 
    raw_query = state.get("query", "").strip()
    t_start   = time.time()
 
    result = run_guardrails(raw_query)
 
    if not result.passed:
        print(f"[pre_hook] BLOCKED — {result.reason}")
        return {
            "guardrail_passed": False,
            "final_summary":    f"⚠️ Request blocked by guardrails: {result.reason}",
            "confidence":       0.0,
            "errors":           [{"node": "pre_hook", "reason": result.reason}],
            "start_time":       t_start,
        }
 
    # Log PII redaction (informational)
    if result.pii_found:
        print(f"[pre_hook] PII detected and redacted in query.")
 
    print(
        f"[pre_hook] Query OK — "
        f"checks: {result.checks_run} | "
        f"pii_found: {result.pii_found}"
    )
 
    return {
        "query":            result.cleaned_query,   # PII-cleaned version
        "guardrail_passed": True,
        "start_time":       t_start,
    }
 
 
# ══════════════════════════════════════════════════════════════════════════
# DAY 13 UPGRADE: supervisor_node  (was: keyword classifier)
#                                   now: GPT-4o structured output
# ══════════════════════════════════════════════════════════════════════════
 
from graph.intent  import classify_intent_gpt
from graph.routing import INTENT_AGENT_MAP
 
 
def supervisor_node(state: AgentState) -> dict:
    """
    GPT-4o powered intent classification + agent routing.
 
    Uses classify_intent_gpt() which:
      • Calls GPT-4o with Pydantic structured output when API key is set
      • Falls back to keyword matching otherwise
    """
    query = state["query"]
 
    # GPT-4o structured classification
    classification = classify_intent_gpt(query)
 
    intent   = classification.intent.value
    products = (
        state.get("data_products")          # user pre-selected
        or classification.data_products      # LLM extracted
        or []
    )
    agents = INTENT_AGENT_MAP.get(intent, ["information", "knowledge"])
 
    print(
        f"[supervisor] intent={intent} | "
        f"confidence={classification.confidence:.2f} | "
        f"products={products} | "
        f"agents={agents}\n"
        f"  reasoning: {classification.reasoning}"
    )
 
    return {
        "intent":        intent,
        "next_agents":   agents,
        "data_products": products,
        # Surface GPT-4o confidence in state (synthesizer will use it)
        "confidence":    classification.confidence,
    }
 
 
# ── Agent nodes (unchanged from Day 12) ───────────────────────────────────
 
def information_node(state: AgentState) -> dict:
    result = _agents["information"].execute(_build_request(state))
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
        "anomalies":     result.data.get("anomalies", []) if result.success else [],
    }
 
 
def knowledge_node(state: AgentState) -> dict:
    result = _agents["knowledge"].execute(_build_request(state))
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
    }
 
 
def metadata_node(state: AgentState) -> dict:
    result = _agents["metadata"].execute(_build_request(state))
    return {
        "agent_results": [result.to_dict()],
        "sources":       result.sources,
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
 
 
# ── Auto-ticket node (unchanged from Day 12) ──────────────────────────────
 
def auto_ticket_node(state: AgentState) -> dict:
    """Create Jira tickets for critical anomalies found by agents."""
    anomalies = state.get("anomalies", [])
    products  = state.get("data_products", ["unknown"])
    created   = []
 
    capacity = _agents["capacity"]
    for anomaly in anomalies:
        if any(kw in anomaly.lower()
               for kw in ["threshold", "missing", "below", "risk"]):
            result = capacity.create_ticket_from_anomaly(anomaly, products[0])
            if result.success:
                created.append(result.data.get("ticket_id", "?"))
 
    return {"auto_tickets": created}
 
 
# ══════════════════════════════════════════════════════════════════════════
# DAY 13 UPGRADE: synthesizer_node  (was: "\n\n---\n\n".join(summaries))
#                                    now: GPT-4o narrative synthesis
# ══════════════════════════════════════════════════════════════════════════
 
_SYNTH_SYSTEM = """\
You are the final synthesis layer of an enterprise Data Governance AI Copilot.
Your job: combine results from multiple specialist agents into one clear,
executive-quality answer for a business analyst.
 
Guidelines:
  • Answer the user's original question directly in the first paragraph.
  • Use ONLY the agent results provided — never hallucinate facts or numbers.
  • Structure your response with markdown:
      - Use **bold** for key metrics and numbers.
      - Use bullet points for lists of findings.
      - Use ## section headers only when there are 3+ distinct topics.
  • Flag anomalies with ⚠️ and tickets with 🎫.
  • End with a short "**Next steps:**" section only when actionable follow-up
    is obvious from the data.
  • Target length: 120–300 words. Be concise.
  • If no agents returned useful results, say so honestly.
"""
 
_SYNTH_HUMAN = """\
Original query: {query}
Detected intent: {intent}
Data products in scope: {products}
 
Agent results:
{agent_context}
 
Auto-created tickets (if any): {tickets}
 
Synthesize a clear, accurate answer to the original query.
"""
 
# Lazy singleton for synthesizer LLM
_synth_llm = None
 
 
def _get_synth_llm():
    global _synth_llm
    if _synth_llm is None:
        from langchain_openai import ChatOpenAI
        _synth_llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.2,          # slight creativity for readable prose
            api_key=os.getenv("OPENAI_API_KEY", ""),
            tags=["synthesizer"],     # LangSmith grouping
        )
    return _synth_llm
 
 
def synthesizer_node(state: AgentState) -> dict:
    """
    GPT-4o powered synthesis of all agent results into a single response.
 
    Falls back to the Day 12 string-join approach when the API key is absent
    so the app never crashes in mock/dev mode.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
 
    results   = state.get("agent_results", [])
    query     = state["query"]
    intent    = state.get("intent", "unknown")
    products  = state.get("data_products", [])
    tickets   = state.get("auto_tickets", [])
 
    # Build agent context block
    successful = [r for r in results if r.get("success") and r.get("summary")]
    agent_context = "\n\n".join(
        f"### {r['agent']}\n{r['summary']}" for r in successful
    ) if successful else "No agents returned successful results."
 
    # ── Compute confidence from agent scores ───────────────────────────
    scores = [r.get("confidence", 0.0) for r in results if r.get("success")]
    # Blend supervisor intent confidence with agent scores
    supervisor_conf = state.get("confidence", 0.0)
    all_scores      = ([supervisor_conf] if supervisor_conf else []) + scores
    avg_confidence  = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
 
    # ── GPT-4o synthesis (with fallback) ──────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY", "")
 
    if not api_key or not successful:
        # Fallback: Day 12 string join
        parts   = [r.get("summary", "") for r in successful]
        summary = "\n\n---\n\n".join(parts) if parts else "No results found."
    else:
        try:
            llm = _get_synth_llm()
            human_text = _SYNTH_HUMAN.format(
                query         = query,
                intent        = intent,
                products      = ", ".join(products) or "not specified",
                agent_context = agent_context,
                tickets       = ", ".join(tickets) if tickets else "none",
            )
            messages = [
                SystemMessage(content=_SYNTH_SYSTEM),
                HumanMessage(content=human_text),
            ]
            response = llm.invoke(messages)
            summary  = response.content.strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[synthesizer] GPT-4o failed — using string fallback. Error: {exc}")
            parts   = [r.get("summary", "") for r in successful]
            summary = "\n\n---\n\n".join(parts) if parts else "No results found."
 
    # ── Update conversation history (memory) ──────────────────────────
    history_entry = {
        "query":   query,
        "summary": summary[:500],
        "intent":  intent,
        "tickets": tickets,
    }
 
    return {
        "final_summary":        summary,
        "confidence":           avg_confidence,
        "conversation_history": [history_entry],
    }
 
 
# ══════════════════════════════════════════════════════════════════════════
# DAY 13 — NEW NODE: post_hook_node
# Runs last, after synthesizer.  Responsibilities:
#   1. Compute total execution_ms from start_time
#   2. Emit a structured audit-log line (visible in LangSmith)
#   3. (Future) push metrics to Prometheus / CloudWatch
# ══════════════════════════════════════════════════════════════════════════
 
def post_hook_node(state: AgentState) -> dict:
    """
    Execution timing + structured audit log.
    Always runs — even when guardrails blocked the query.
    """
    t_end      = time.time()
    t_start    = state.get("start_time", t_end)
    elapsed_ms = round((t_end - t_start) * 1000, 1)
 
    agents_used = [
        r.get("agent", "?")
        for r in state.get("agent_results", [])
        if r.get("agent")
    ]
 
    print(
        f"[post_hook] query_id={state.get('query_id')} | "
        f"intent={state.get('intent', 'n/a')} | "
        f"guardrail_passed={state.get('guardrail_passed', True)} | "
        f"agents={agents_used} | "
        f"confidence={state.get('confidence', 0.0):.2f} | "
        f"tickets={state.get('auto_tickets', [])} | "
        f"execution_ms={elapsed_ms}"
    )
 
    return {"execution_ms": elapsed_ms}