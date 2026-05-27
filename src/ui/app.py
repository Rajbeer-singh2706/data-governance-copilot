"""
src/ui/app.py
Day 18: Polished Streamlit UI.

New vs Day 15:
  • Confidence progress bar (colour-coded green/amber/red)
  • Source pills displayed as styled chips
  • Anomaly badges with ⚠️ colour coding
  • Agent pill row showing which agents ran
  • Execution stats bar (ms, confidence, intent, agents, turns)
  • Sidebar: live Redis status + daily token budget gauge
  • Error expander with per-node breakdown
  • Better example queries with one-click load
"""
import streamlit as st
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.graph  import copilot_graph
from graph.state  import initial_state
from config.settings import config


# ── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "Data Governance Copilot",
    page_icon  = "🏛️",
    layout     = "wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Source pills */
.pill {
    display: inline-block;
    background: #eef5ff;
    border: 1px solid #b5d4f4;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    color: #185fa5;
    margin: 2px;
}
/* Agent pills */
.agent-pill {
    display: inline-block;
    background: #f0f0f0;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
    color: #555;
    margin: 2px;
}
/* Anomaly badge */
.anomaly-badge {
    background: #fcebeb;
    border-left: 3px solid #E24B4A;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    color: #A32D2D;
    margin: 4px 0;
}
/* Stats bar */
.stat-bar {
    display: flex;
    gap: 1.5rem;
    font-size: 12px;
    color: #666;
    padding: 6px 0;
    border-top: 1px solid #eee;
    margin-top: 8px;
}
.stat-item strong { color: #111; }
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "thread_id":    str(uuid.uuid4()),
        "chat_history": [],
        "last_result":  None,
        "pending_hitl": None,
        "pending_query": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Graph helper ───────────────────────────────────────────────────────────

def run_query(query: str, time_range: str, approved: bool = False) -> dict:
    state = initial_state(
        query     = query,
        thread_id = st.session_state.thread_id,
        user_id   = "streamlit-user",
        time_range = time_range,
    )
    state["approved"] = approved
    return copilot_graph.invoke(
        state,
        config={"configurable": {"thread_id": st.session_state.thread_id}},
    )


# ── UI components ──────────────────────────────────────────────────────────

def _confidence_bar(confidence: float):
    """Render a colour-coded confidence progress bar."""
    pct   = int(confidence * 100)
    color = "#22c55e" if pct >= 80 else "#f59e0b" if pct >= 50 else "#ef4444"
    label = "High" if pct >= 80 else "Medium" if pct >= 50 else "Low"
    st.markdown(
        f"**Confidence:** {label} ({pct}%)"
        f"<div style='background:#e5e7eb;border-radius:6px;height:6px;margin-top:4px'>"
        f"<div style='background:{color};width:{pct}%;height:6px;border-radius:6px'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _source_pills(sources: list):
    """Render sources as styled chip pills."""
    if not sources:
        return
    pills = "".join(f'<span class="pill">📄 {s}</span>' for s in sources[:6])
    st.markdown(f"**Sources:** {pills}", unsafe_allow_html=True)


def _agent_pills(agent_results: list):
    """Show which agents ran as compact pills."""
    agents = [r.get("agent","?") for r in agent_results if r.get("agent")]
    if not agents:
        return
    pills = "".join(f'<span class="agent-pill">🤖 {a}</span>' for a in agents)
    st.markdown(f"**Agents:** {pills}", unsafe_allow_html=True)


def _anomaly_badges(anomalies: list):
    """Render each anomaly as a red-bordered badge."""
    if not anomalies:
        return
    st.markdown("**⚠️ Anomalies detected:**")
    for a in anomalies:
        st.markdown(f'<div class="anomaly-badge">⚠️ {a}</div>',
                    unsafe_allow_html=True)


def _stats_bar(result: dict):
    """One-line execution stats beneath each response."""
    ms       = result.get("execution_ms", 0)
    intent   = result.get("intent", "?")
    conf     = result.get("confidence", 0)
    n_agents = len([r for r in result.get("agent_results",[]) if r.get("agent")])
    n_turns  = len(result.get("conversation_history", []))
    tickets  = result.get("auto_tickets", [])

    stat = (
        f"⏱ **{ms:.0f} ms** &nbsp;·&nbsp; "
        f"🎯 **{intent}** &nbsp;·&nbsp; "
        f"📊 **{conf:.0%}** confidence &nbsp;·&nbsp; "
        f"🤖 **{n_agents}** agents &nbsp;·&nbsp; "
        f"💬 **{n_turns}** turns"
    )
    if tickets:
        stat += f" &nbsp;·&nbsp; 🎫 **{', '.join(tickets)}**"

    st.markdown(
        f'<div class="stat-bar">{stat}</div>',
        unsafe_allow_html=True,
    )


def _render_response(result: dict):
    """Full response rendering with all Day 18 UI components."""
    summary = result.get("final_summary", "")

    st.markdown(summary)
    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        _confidence_bar(result.get("confidence", 0))
    with col2:
        _agent_pills(result.get("agent_results", []))

    _anomaly_badges(result.get("anomalies", []))
    _source_pills(result.get("sources", []))
    _stats_bar(result)

    # Errors expander
    errors = result.get("errors", [])
    if errors:
        with st.expander(f"⚠️ {len(errors)} agent error(s)"):
            for e in errors:
                st.error(f"**{e.get('node','?')}:** {e.get('error','unknown')}")

    # Raw data expander
    data = next(
        (r.get("data",{}) for r in result.get("agent_results",[])
         if r.get("agent") == "information_agent" and r.get("success")),
        {},
    )
    if data:
        with st.expander("📊 Raw metrics"):
            st.json(data)


# ── HITL panel ─────────────────────────────────────────────────────────────

def _render_hitl_panel():
    hitl = st.session_state.pending_hitl
    if not hitl:
        return

    st.divider()
    with st.container(border=True):
        st.markdown("### 🔔 Action requires your approval")
        st.warning(hitl["message"])
        for a in hitl["anomalies"]:
            st.markdown(f'<div class="anomaly-badge">⚠️ {a}</div>',
                        unsafe_allow_html=True)
        st.caption(f"Data products: {', '.join(hitl['products'])}")

        col1, col2 = st.columns(2)
        if col1.button("✅ Approve — Create Jira tickets",
                       use_container_width=True, type="primary"):
            with st.spinner("Creating tickets..."):
                raw = run_query(hitl["query"], hitl["time_range"], approved=True)
            tickets = raw.get("auto_tickets", [])
            if tickets:
                st.success(f"🎫 Created: {', '.join(tickets)}")
            st.session_state.pending_hitl = None
            st.rerun()

        if col2.button("❌ Reject", use_container_width=True):
            st.session_state.pending_hitl = None
            st.info("Ticket creation rejected.")
            st.rerun()
    st.divider()


# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    mock_mode  = st.toggle("Mock Mode", value=config.enable_mock,
                            help="No real API keys needed")
    time_range = st.selectbox("Time Range",
                               ["last_month","last_quarter","last_week","YTD"])

    st.divider()
    st.markdown("## 🧠 Memory")
    st.caption(f"Thread: `{st.session_state.thread_id[:20]}...`")
    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.update({
            "thread_id":    str(uuid.uuid4()),
            "chat_history": [],
            "last_result":  None,
            "pending_hitl": None,
        })
        st.rerun()

    # Redis + token status
    st.divider()
    st.markdown("## 📡 System")
    try:
        from core.cache    import get_client
        from core.llm_guard import get_daily_usage
        redis  = get_client(config.redis)
        redis_ok = bool(redis and redis.ping())
        usage  = get_daily_usage(redis)

        st.markdown(
            f"**Redis:** {'🟢 Connected' if redis_ok else '🔴 Offline (in-memory fallback)'}"
        )
        pct = usage.get("pct", 0)
        st.markdown(f"**Daily tokens:** {usage.get('tokens_used',0):,} / {usage.get('limit',0):,} ({pct}%)")
        if pct > 0:
            st.progress(min(pct / 100, 1.0))
    except Exception:
        st.caption("System status unavailable")

    st.divider()
    st.markdown("## 💡 Examples")
    examples = [
        "Why did retention drop last month?",
        "Who owns the bookings dataset?",
        "What is GRR and how is it calculated?",
        "Show open Jira bugs for CAC data",
        "Create a DQ rule for null check on LTV",
        "Compare retention vs LTV trends",
    ]
    for ex in examples:
        if st.button(f"↪ {ex[:40]}", key=f"ex_{ex[:15]}",
                     use_container_width=True):
            st.session_state.pending_query = ex

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.update({
            "chat_history": [], "last_result": None, "pending_hitl": None
        })
        st.rerun()


# ── Header ─────────────────────────────────────────────────────────────────

st.markdown(
    "# 🏛️ Data Governance Copilot\n"
    "_Multi-agent AI · LangGraph · LiteLLM · pgvector · Redis · Teams_"
)
st.divider()

# ── Chat history ────────────────────────────────────────────────────────────

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            st.markdown(msg["content"])
            if "result" in msg:
                _render_response(msg["result"])

# ── HITL panel ──────────────────────────────────────────────────────────────

_render_hitl_panel()

# ── Chat input ──────────────────────────────────────────────────────────────

pending = st.session_state.pop("pending_query", None)
query   = st.chat_input("Ask about your data products...") or pending

if query:
    st.session_state.chat_history.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Routing to agents..."):
            try:
                raw = run_query(query, time_range)
            except Exception as e:
                st.error(f"Graph error: {e}")
                st.stop()

        summary = raw.get("final_summary", "No response.")
        st.markdown(summary)
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            _confidence_bar(raw.get("confidence", 0))
        with col2:
            _agent_pills(raw.get("agent_results", []))
        _anomaly_badges(raw.get("anomalies", []))
        _source_pills(raw.get("sources", []))
        _stats_bar(raw)

        errors = raw.get("errors", [])
        if errors:
            with st.expander(f"⚠️ {len(errors)} agent error(s)"):
                for e in errors:
                    st.error(f"**{e.get('node','?')}:** {e.get('error','unknown')}")

        # HITL check
        if raw.get("pending_action"):
            st.session_state.pending_hitl = {
                **raw["pending_action"],
                "query":      query,
                "time_range": time_range,
            }
            st.info(f"🔔 {raw['pending_action']['message']}")
            st.rerun()

    st.session_state.chat_history.append({
        "role":    "assistant",
        "content": summary,
        "result":  raw,
    })
    st.session_state.last_result = raw