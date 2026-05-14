import streamlit as st 
import sys 
from pathlib import Path

# Add src/ to path so imports work when running from ui/
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.supervisor_agent import SupervisorAgent
from config.settings import config

# ── Page config ─────────────────────────────────────────
st.set_page_config(
    page_title = "Data Governance Copilot",
    page_icon  = "🏛️",
    layout     = "wide",
)


# ── Session state ───────────────────────────────────────
# Initialise once — persists between reruns
if "supervisor" not in st.session_state:
    st.session_state.supervisor = SupervisorAgent(
        enable_mock=config.enable_mock
    )

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Header ──────────────────────────────────────────────
st.title("🏛️ Data Governance Copilot")
st.caption("Ask questions about your enterprise data products")
st.divider()

# ── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    mock_mode = st.toggle(
        "Mock Mode",
        value=config.enable_mock,
        help="Use simulated data — no real credentials needed"
    )
    if mock_mode != config.enable_mock:
        config.enable_mock = mock_mode
        st.session_state.supervisor = SupervisorAgent(
            enable_mock=mock_mode
        )
        st.rerun()

    time_range = st.selectbox(
        "Time Range",
        ["last_month", "last_quarter", "last_week", "YTD"],
        index=0,
    )

    st.divider()
    st.header("💡 Try these")
    examples = [
        "Why did retention drop last month?",
        "Show me bookings metrics",
        "What is our CAC payback period?",
        "Show LTV breakdown by segment",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.pending_query = ex

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ── Chat history ────────────────────────────────────────
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "details" in msg:
            d = msg["details"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Confidence", f"{d['confidence']:.0%}")
            col2.metric("Agents Used", len(d["agents_used"]))
            col3.metric("Mock Mode",
                        "ON" if config.enable_mock else "OFF")
            if d.get("anomalies"):
                st.warning(
                    "**Anomalies detected:**\n" +
                    "\n".join(d["anomalies"])
                )
            with st.expander("📊 Raw metrics"):
                st.json(d.get("data", {}))
            with st.expander("📚 Sources"):
                for s in d.get("sources", []):
                    st.write(f"• {s}")


# ── Query input ─────────────────────────────────────────
pending = st.session_state.pop("pending_query", None)
query   = st.chat_input(
    "Ask about your data products...",
) or pending

if query:
    # Show user message
    st.session_state.chat_history.append({
        "role":    "user",
        "content": query,
    })
    with st.chat_message("user"):
        st.markdown(query)

    # Run supervisor and show response
    with st.chat_message("assistant"):
        with st.spinner("Analysing your data..."):
            response = st.session_state.supervisor.run(
                query      = query,
                time_range = time_range,
            )

        if response.success:
            st.markdown(response.summary)
            col1, col2, col3 = st.columns(3)
            col1.metric("Confidence",
                        f"{response.confidence:.0%}")
            col2.metric("Agents Used",
                        len(response.agents_used))
            col3.metric("Mock Mode",
                        "ON" if config.enable_mock else "OFF")
            if response.anomalies:
                st.warning(
                    "**Anomalies detected:**\n" +
                    "\n".join(response.anomalies)
                )
            with st.expander("📊 Raw metrics"):
                st.json(response.data)
            with st.expander("📚 Sources"):
                for s in response.sources:
                    st.write(f"• {s}")
        else:
            st.error(f"Error: {response.error}")

    # Save to chat history
    st.session_state.chat_history.append({
        "role":    "assistant",
        "content": response.summary,
        "details": {
            "confidence": response.confidence,
            "agents_used": response.agents_used,
            "anomalies":   response.anomalies,
            "data":        response.data,
            "sources":     response.sources,
        }
    })