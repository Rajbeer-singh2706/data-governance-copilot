"""
src/ui/app.py
Day 15 additions:
  • HITL approval panel — shown when pending_action is set in graph result
  • Error summary — surfaces agent errors from state["errors"]
  • Execution metadata sidebar — shows per-run stats
"""
import streamlit as st
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.graph import copilot_graph
from graph.state import initial_state
from config.settings import config


# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Data Governance Copilot",
    page_icon="🏛️",
    layout="wide",
)


# Add custom CSS block after st.set_page_config():
st.markdown("""
<style>
.pill { display:inline-block; background:#eef5ff; border:1px solid #b5d4f4;
        border-radius:20px; padding:2px 10px; font-size:12px; color:#185fa5; margin:2px; }
.agent-pill { display:inline-block; background:#f0f0f0; border-radius:20px;
              padding:2px 10px; font-size:11px; color:#555; margin:2px; }
.anomaly-badge { background:#fcebeb; border-left:3px solid #E24B4A;
                 border-radius:4px; padding:6px 10px; font-size:13px;
                 color:#A32D2D; margin:4px 0; }
</style>
""", unsafe_allow_html=True)

# Add _confidence_bar(), _source_pills(), _anomaly_badges(), _stats_bar()
# Add Redis + token gauge to sidebar
# See full app.py in the downloadable files

# ── Session state ─────────────────────────────────────────────────────────

if "thread_id"    not in st.session_state:
    st.session_state.thread_id    = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_result"  not in st.session_state:
    st.session_state.last_result  = None
if "pending_hitl" not in st.session_state:
    st.session_state.pending_hitl = None   # Day 15: HITL state


# ── Helpers ───────────────────────────────────────────────────────────────

def _config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def run_query(query: str, time_range: str, approved: bool = False) -> dict:
    """Run query through LangGraph. Pass approved=True to confirm HITL."""
    state = initial_state(
        query      = query,
        thread_id  = st.session_state.thread_id,
        user_id    = "streamlit-user",
        time_range = time_range,
        approved   = approved,          # Day 15: HITL flag
    )
    return copilot_graph.invoke(state, config=_config())


class GraphResponse:
    def __init__(self, result: dict):
        self.summary        = result.get("final_summary", "")
        self.intent         = result.get("intent", "unknown")
        self.confidence     = result.get("confidence", 0.0)
        self.sources        = result.get("sources", [])
        self.auto_tickets   = result.get("auto_tickets", [])
        self.anomalies      = result.get("anomalies", [])
        self.errors         = result.get("errors", [])
        self.pending_action = result.get("pending_action")      # Day 15
        self.execution_ms   = result.get("execution_ms", 0.0)  # Day 15
        self.success        = bool(self.summary)
        self.agents_used    = [
            r.get("agent", "") for r in result.get("agent_results", [])
            if r.get("agent")
        ]
        self.data           = next(
            (r.get("data", {}) for r in result.get("agent_results", [])
             if r.get("agent") == "information_agent" and r.get("success")),
            {},
        )
        self.memory_turns   = len(result.get("conversation_history", []))


def _render_response_meta(response: GraphResponse):
    """Shared metrics + expanders for both chat history and live response."""
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Confidence",  f"{response.confidence:.0%}")
    col2.metric("Agents",      len(response.agents_used))
    col3.metric("Intent",      response.intent)
    col4.metric("Exec ms",     f"{response.execution_ms:.0f}")
    col5.metric("Memory",      f"{response.memory_turns} turns")

    if response.anomalies:
        st.warning("**⚠️ Anomalies detected:**\n" + "\n".join(f"• {a}" for a in response.anomalies))

    if response.auto_tickets:
        st.success("**🎫 Tickets created:** " + ", ".join(response.auto_tickets))

    if response.errors:
        with st.expander(f"⚠️ {len(response.errors)} agent error(s)"):
            for e in response.errors:
                st.error(f"**{e.get('node','?')}:** {e.get('error','unknown error')}")

    with st.expander("📊 Raw metrics"):
        st.json(response.data)
    with st.expander("📚 Sources"):
        for s in response.sources:
            st.write(f"• {s}")
    with st.expander("🤖 Agents used"):
        for a in response.agents_used:
            st.write(f"• {a}")


# ══════════════════════════════════════════════════════════════════════════
# DAY 15 — HITL approval panel
# Shown when auto_ticket_node sets pending_action
# ══════════════════════════════════════════════════════════════════════════

def _render_hitl_panel():
    """
    If a pending HITL action exists, show an approval card above the chat input.
    Approve → re-run graph with approved=True
    Reject  → clear pending, continue
    """
    hitl = st.session_state.pending_hitl
    if not hitl:
        return

    st.divider()
    with st.container(border=True):
        st.markdown("### 🔔 Action requires your approval")
        st.warning(hitl["message"])

        st.markdown("**Anomalies detected:**")
        for a in hitl["anomalies"]:
            st.markdown(f"• {a}")

        st.markdown(f"*Data products: {', '.join(hitl['products'])}*")
        st.markdown(f"*Tickets to create: {hitl['count']}*")

        col1, col2 = st.columns(2)

        if col1.button("✅ Approve — Create Jira tickets", use_container_width=True, type="primary"):
            with st.spinner("Creating Jira tickets..."):
                try:
                    raw = run_query(
                        query      = hitl["query"],
                        time_range = hitl["time_range"],
                        approved   = True,
                    )
                    response = GraphResponse(raw)

                    if response.auto_tickets:
                        st.success(f"🎫 Created: {', '.join(response.auto_tickets)}")
                    else:
                        st.info("No tickets created.")

                    # Add to chat history
                    st.session_state.chat_history.append({
                        "role":    "assistant",
                        "content": f"✅ Approved. Created tickets: {', '.join(response.auto_tickets) or 'none'}",
                        "meta":    {
                            "confidence": response.confidence,
                            "agents_used": response.agents_used,
                            "intent": response.intent,
                            "memory_turns": response.memory_turns,
                            "anomalies": response.anomalies,
                            "auto_tickets": response.auto_tickets,
                            "data": response.data,
                            "sources": response.sources,
                            "errors": response.errors,
                            "execution_ms": response.execution_ms,
                        },
                    })
                except Exception as e:
                    st.error(f"Ticket creation failed: {e}")

            st.session_state.pending_hitl = None
            st.rerun()

        if col2.button("❌ Reject — Skip ticket creation", use_container_width=True):
            st.session_state.pending_hitl = None
            st.info("Ticket creation rejected.")
            st.rerun()

    st.divider()


# ── Header ────────────────────────────────────────────────────────────────

st.title("🏛️ Data Governance Copilot")
st.caption(
    "Multi-agent AI assistant · LangGraph · "
    "LiteLLM fallback · Redis cache · Human-in-the-loop"
)
st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")

    st.caption("🔌 Live mode — configure credentials in .env")

    time_range = st.selectbox(
        "Time Range",
        ["last_month", "last_quarter", "last_week", "YTD"],
        index=0,
    )

    st.divider()
    st.header("🧠 Memory")
    st.caption(f"Thread: `{st.session_state.thread_id[:16]}...`")

    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.thread_id    = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.session_state.last_result  = None
        st.session_state.pending_hitl = None
        st.rerun()

    st.divider()
    st.header("💡 Try these")
    examples = [
        "Why did retention drop last month?",
        "Who owns the bookings dataset?",
        "Show open Jira bugs for retention",
        "What is GRR and how is it calculated?",
        "Create a bug ticket for EU data missing",
        "List all data quality rules",
        "Show me CAC payback metrics",
    ]
    for ex in examples:
        if st.button(f"↪ {ex[:42]}", key=f"ex_{ex[:20]}", use_container_width=True):
            st.session_state.pending_query = ex

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_result  = None
        st.session_state.pending_hitl = None
        st.rerun()


# ── Chat history ──────────────────────────────────────────────────────────

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "meta" in msg:
            # Quick inline meta for history items
            meta = msg["meta"]
            cols = st.columns(4)
            cols[0].metric("Confidence", f"{meta['confidence']:.0%}")
            cols[1].metric("Agents",     len(meta["agents_used"]))
            cols[2].metric("Intent",     meta["intent"])
            cols[3].metric("Exec ms",    f"{meta.get('execution_ms',0):.0f}")

            if meta.get("anomalies"):
                st.warning("**Anomalies:** " + ", ".join(meta["anomalies"]))
            if meta.get("auto_tickets"):
                st.success("**Tickets:** " + ", ".join(meta["auto_tickets"]))
            if meta.get("errors"):
                st.error(f"{len(meta['errors'])} agent error(s)")


# ── HITL panel (Day 15) ───────────────────────────────────────────────────

_render_hitl_panel()


# ── Query input ───────────────────────────────────────────────────────────

pending = st.session_state.pop("pending_query", None)
query   = st.chat_input("Ask about your data products...") or pending

if query:
    st.session_state.chat_history.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Orchestrating agents..."):
            try:
                raw_result = run_query(query, time_range)
                response   = GraphResponse(raw_result)
            except Exception as e:
                st.error(f"Graph execution failed: {e}")
                st.stop()

        if response.success:
            st.markdown(response.summary)
            _render_response_meta(response)

            # ── Day 15: HITL check ─────────────────────────────────────
            if response.pending_action:
                st.session_state.pending_hitl = {
                    **response.pending_action,
                    "query":      query,
                    "time_range": time_range,
                }
                st.info(
                    f"🔔 **Approval needed:** {response.pending_action['message']}\n\n"
                    "Scroll up to see the approval panel."
                )
                st.rerun()   # re-render so HITL panel appears above chat input
        else:
            st.error("No response generated. Check agent logs.")

    st.session_state.chat_history.append({
        "role":    "assistant",
        "content": response.summary if response.success else "No response generated.",
        "meta": {
            "confidence":   response.confidence,
            "agents_used":  response.agents_used,
            "intent":       response.intent,
            "memory_turns": response.memory_turns,
            "anomalies":    response.anomalies,
            "auto_tickets": response.auto_tickets,
            "data":         response.data,
            "sources":      response.sources,
            "errors":       response.errors,
            "execution_ms": response.execution_ms,
        },
    })

    st.session_state.last_result = raw_result
