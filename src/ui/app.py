import streamlit as st
import sys
import uuid
from pathlib import Path

# Add src/ to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.graph import copilot_graph
from graph.state import initial_state
from config.settings import config


# ── Page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="Data Governance Copilot",
    page_icon="🏛️",
    layout="wide",
)

# ── Session state ────────────────────────────────────────────
# Thread ID = conversation identifier for LangGraph memory
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None


# ── Helper: run query through LangGraph ─────────────────────
def run_query(query: str, time_range: str) -> dict:
    """Invoke the LangGraph graph and return raw result dict."""
    config_dict = {
        "configurable": {
            "thread_id": st.session_state.thread_id
        }
    }
    state = initial_state(
        query      = query,
        thread_id  = st.session_state.thread_id,
        user_id    = "streamlit-user",
        time_range = time_range,
    )
    return copilot_graph.invoke(state, config=config_dict)


# ── Helper: wrap raw graph result for display ────────────────
class GraphResponse:
    """
    Wraps the raw LangGraph result dict into
    a simple object the UI can use.
    """
    def __init__(self, result: dict):
        self.summary      = result.get("final_summary", "")
        self.intent       = result.get("intent", "unknown")
        self.confidence   = result.get("confidence", 0.0)
        self.sources      = result.get("sources", [])
        self.auto_tickets = result.get("auto_tickets", [])
        self.anomalies    = result.get("anomalies", [])
        self.success      = bool(self.summary)

        # Extract agent names from accumulated results
        self.agents_used = [
            r.get("agent", "")
            for r in result.get("agent_results", [])
            if r.get("agent")
        ]

        # Extract raw metrics data from information_agent result
        self.data = next(
            (
                r.get("data", {})
                for r in result.get("agent_results", [])
                if r.get("agent") == "information_agent"
                and r.get("success")
            ),
            {},
        )

        # Conversation history length (memory indicator)
        self.memory_turns = len(
            result.get("conversation_history", [])
        )


# ── Header ───────────────────────────────────────────────────
st.title("🏛️ Data Governance Copilot")
st.caption(
    "Multi-agent AI assistant powered by LangGraph · "
    "Ask questions about your enterprise data products"
)
st.divider()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    mock_mode = st.toggle(
        "Mock Mode",
        value=config.enable_mock,
        help="Use simulated data — no real credentials needed",
    )
    if mock_mode != config.enable_mock:
        config.enable_mock = mock_mode
        st.rerun()

    time_range = st.selectbox(
        "Time Range",
        ["last_month", "last_quarter", "last_week", "YTD"],
        index=0,
    )

    st.divider()

    # Memory controls
    st.header("🧠 Memory")
    st.caption(f"Thread ID: `{st.session_state.thread_id[:16]}...`")

    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.thread_id   = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.session_state.last_result  = None
        st.rerun()

    st.divider()

    # Example queries
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
        if st.button(
            f"↪ {ex[:42]}{'...' if len(ex)>42 else ''}",
            key=f"ex_{ex[:20]}",
            use_container_width=True,
        ):
            st.session_state.pending_query = ex

    st.divider()

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_result  = None
        st.rerun()


# ── Chat history ─────────────────────────────────────────────
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and "meta" in msg:
            meta = msg["meta"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Confidence",  f"{meta['confidence']:.0%}")
            col2.metric("Agents Used", len(meta["agents_used"]))
            col3.metric("Intent",      meta["intent"])
            col4.metric("Memory",      f"{meta['memory_turns']} turns")

            if meta.get("anomalies"):
                st.warning(
                    "**Anomalies detected:**\n"
                    + "\n".join(meta["anomalies"])
                )

            if meta.get("auto_tickets"):
                st.success(
                    "**Auto-created tickets:** "
                    + ", ".join(meta["auto_tickets"])
                )

            with st.expander("📊 Raw metrics"):
                st.json(meta.get("data", {}))

            with st.expander("📚 Sources"):
                for s in meta.get("sources", []):
                    st.write(f"• {s}")

            with st.expander("🤖 Agents used"):
                for a in meta.get("agents_used", []):
                    st.write(f"• {a}")


# ── Query input ──────────────────────────────────────────────
pending = st.session_state.pop("pending_query", None)
query   = st.chat_input("Ask about your data products...") or pending

if query:
    # Show user message
    st.session_state.chat_history.append({
        "role":    "user",
        "content": query,
    })
    with st.chat_message("user"):
        st.markdown(query)

    # Run through LangGraph
    with st.chat_message("assistant"):
        with st.spinner("🔍 Orchestrating agents via LangGraph..."):
            try:
                raw_result = run_query(query, time_range)
                response   = GraphResponse(raw_result)
            except Exception as e:
                st.error(f"Graph execution failed: {e}")
                st.stop()

        if response.success:
            st.markdown(response.summary)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Confidence",  f"{response.confidence:.0%}")
            col2.metric("Agents Used", len(response.agents_used))
            col3.metric("Intent",      response.intent)
            col4.metric("Memory",      f"{response.memory_turns} turns")

            if response.anomalies:
                st.warning(
                    "**Anomalies detected:**\n"
                    + "\n".join(response.anomalies)
                )

            if response.auto_tickets:
                st.success(
                    "**Auto-created tickets:** "
                    + ", ".join(response.auto_tickets)
                )

            with st.expander("📊 Raw metrics"):
                st.json(response.data)

            with st.expander("📚 Sources"):
                for s in response.sources:
                    st.write(f"• {s}")

            with st.expander("🤖 Agents used"):
                for a in response.agents_used:
                    st.write(f"• {a}")
        else:
            st.error("No response generated. Check agent logs.")

    # Save to chat history
    st.session_state.chat_history.append({
        "role":    "assistant",
        "content": response.summary if response.success
                   else "No response generated.",
        "meta": {
            "confidence":   response.confidence,
            "agents_used":  response.agents_used,
            "intent":       response.intent,
            "memory_turns": response.memory_turns,
            "anomalies":    response.anomalies,
            "auto_tickets": response.auto_tickets,
            "data":         response.data,
            "sources":      response.sources,
        },
    })
    
    st.session_state.last_result = raw_result