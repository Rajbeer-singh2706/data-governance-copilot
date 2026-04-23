"""
Data Governance Copilot — Streamlit Web UI
==========================================
A production-ready conversational interface for the multi-agent system.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import streamlit as st
from datetime import datetime

from config.settings import config, DATA_PRODUCTS
from agents.supervisor_agent import SupervisorAgent, SupervisorResponse


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Data Governance Copilot",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    .stApp { background: #0f1117; }

    .main-header {
        background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
        border: 1px solid #2a3441;
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 24px;
    }
    .main-header h1 { color: #e2e8f0; font-weight: 600; font-size: 1.8rem; margin: 0; }
    .main-header p { color: #64748b; font-size: 0.9rem; margin: 4px 0 0; }

    .agent-card {
        background: #161b27;
        border: 1px solid #2a3441;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
    .agent-card.success { border-left: 3px solid #22c55e; }
    .agent-card.error   { border-left: 3px solid #ef4444; }
    .agent-card h4      { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 8px; }
    .agent-card p       { color: #cbd5e1; font-size: 0.85rem; margin: 0; line-height: 1.5; }

    .summary-box {
        background: #161b27;
        border: 1px solid #3b82f6;
        border-radius: 10px;
        padding: 20px 24px;
        margin: 16px 0;
    }
    .summary-box h3 { color: #60a5fa; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.5px; margin: 0 0 12px; }

    .metric-chip {
        display: inline-block;
        background: #1e2940;
        color: #60a5fa;
        border: 1px solid #2a4a8a;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.75rem;
        margin: 3px;
        font-family: 'IBM Plex Mono', monospace;
    }

    .action-item {
        background: #1a2535;
        border-left: 3px solid #f59e0b;
        border-radius: 0 6px 6px 0;
        padding: 8px 14px;
        margin: 6px 0;
        color: #fcd34d;
        font-size: 0.85rem;
    }

    .ticket-badge {
        background: #14532d;
        color: #4ade80;
        border: 1px solid #166534;
        border-radius: 4px;
        padding: 2px 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
    }

    .chat-user {
        background: #1e2940;
        border-radius: 12px 12px 4px 12px;
        padding: 12px 16px;
        margin: 8px 0 8px auto;
        max-width: 70%;
        color: #e2e8f0;
        font-size: 0.9rem;
    }
    .chat-assistant {
        background: #161b27;
        border: 1px solid #2a3441;
        border-radius: 12px 12px 12px 4px;
        padding: 12px 16px;
        margin: 8px auto 8px 0;
        max-width: 85%;
        color: #cbd5e1;
        font-size: 0.9rem;
    }

    .stTextInput > div > div > input {
        background: #161b27 !important;
        color: #e2e8f0 !important;
        border: 1px solid #2a3441 !important;
        border-radius: 8px !important;
    }
    .stButton > button {
        background: #2563eb !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500;
    }
    .stButton > button:hover { background: #1d4ed8 !important; }

    .sidebar-section {
        background: #161b27;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    div[data-testid="metric-container"] {
        background: #161b27;
        border: 1px solid #2a3441;
        border-radius: 8px;
        padding: 12px;
    }
    .stMetric label { color: #64748b !important; font-size: 0.75rem !important; }
    .stMetric [data-testid="metric-value"] { color: #e2e8f0 !important; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f1117; }
    ::-webkit-scrollbar-thumb { background: #2a3441; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "supervisor" not in st.session_state:
    st.session_state.supervisor = SupervisorAgent(config=config, enable_mock=config.enable_mock)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_response" not in st.session_state:
    st.session_state.last_response = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="main-header"><h1>🏛️ DG Copilot</h1><p>Data Governance Assistant</p></div>', unsafe_allow_html=True)

    st.markdown("### ⚙️ Configuration")
    mock_mode = st.toggle("Mock Mode", value=config.enable_mock, help="Use simulated data sources")
    if mock_mode != config.enable_mock:
        config.enable_mock = mock_mode
        st.session_state.supervisor = SupervisorAgent(config=config, enable_mock=mock_mode)
        st.rerun()

    time_range = st.selectbox("Time Range", ["last_month", "last_quarter", "last_week", "YTD", "Q3_2024"], index=0)

    st.markdown("### 📦 Data Products")
    selected_products = st.multiselect(
        "Focus on:",
        options=list(DATA_PRODUCTS.keys()),
        default=[],
        help="Leave empty for auto-detection",
    )

    st.markdown("### 💡 Example Queries")
    examples = [
        "Why did retention drop last month?",
        "What is the data quality score for CAC?",
        "Who owns the bookings dataset?",
        "Show me open Jira issues for retention",
        "What is GRR and how is it calculated?",
        "Create a DQ rule for retention completeness",
        "Create a bug ticket for missing EU data",
        "Show all active data quality rules",
    ]
    for example in examples:
        if st.button(f"↪ {example[:45]}...", key=f"ex_{example[:20]}", use_container_width=True):
            st.session_state.pending_query = example

    st.markdown("---")
    health = st.session_state.supervisor.health_check()
    st.markdown("### 🔍 Agent Status")
    for agent_name, agent_health in health["agents"].items():
        icon = "🟢" if agent_health.get("healthy") else "🔴"
        st.markdown(f"{icon} `{agent_name}`")


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h1>🏛️ Data Governance Copilot</h1>
    <p>Multi-agent AI assistant for data metrics, governance, quality, and operations</p>
</div>
""", unsafe_allow_html=True)

# Metrics row
col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("Agents Active", "5", "All Healthy")
with col2: st.metric("Data Products", "4", "Bookings, Retention, LTV, CAC")
with col3: st.metric("Mock Mode", "ON" if config.enable_mock else "OFF")
with col4: st.metric("Avg Response", "~1.2s")
with col5: st.metric("Queries Today", str(len(st.session_state.chat_history)))

st.markdown("---")

# Chat history
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-user">💬 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        with st.container():
            resp: SupervisorResponse = msg.get("response")
            if resp:
                render_response(resp)

# Query input
def render_response(resp: SupervisorResponse):
    """Render a SupervisorResponse in the chat UI."""
    st.markdown(f"""
    <div class="summary-box">
        <h3>🤖 Copilot Response</h3>
        <p style="color:#94a3b8; font-size:0.75rem; margin-bottom:12px;">
            Intent: <code>{resp.intent}</code> &nbsp;|&nbsp; 
            Confidence: <code>{resp.overall_confidence:.0%}</code> &nbsp;|&nbsp; 
            Time: <code>{resp.execution_time_ms}ms</code>
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(resp.final_summary)

    # Agent results in expander
    with st.expander("📡 Agent Breakdown", expanded=False):
        for ar in resp.agent_results:
            css_class = "success" if ar["success"] else "error"
            st.markdown(f"""
            <div class="agent-card {css_class}">
                <h4>{ar['agent']} — {ar['execution_time_ms']}ms | confidence: {ar.get('confidence', 0):.0%}</h4>
                <p>{ar['summary'][:300]}{'...' if len(ar.get('summary','')) > 300 else ''}</p>
            </div>
            """, unsafe_allow_html=True)

    # Auto-created tickets
    if resp.auto_created_tickets:
        st.markdown("**🎫 Auto-created Tickets:**")
        for ticket_id in resp.auto_created_tickets:
            st.markdown(f'<span class="ticket-badge">✅ {ticket_id}</span>', unsafe_allow_html=True)

    # Recommended actions
    if resp.recommended_actions:
        st.markdown("**📋 Recommended Actions:**")
        for action in resp.recommended_actions:
            st.markdown(f'<div class="action-item">→ {action}</div>', unsafe_allow_html=True)

    # Data products referenced
    if resp.data_products_referenced:
        st.markdown("**Referenced Data Products:**")
        chips = "".join(f'<span class="metric-chip">{p}</span>' for p in resp.data_products_referenced)
        st.markdown(chips, unsafe_allow_html=True)


# Handle pending query from sidebar buttons
pending = st.session_state.pop("pending_query", None)

with st.form("query_form", clear_on_submit=True):
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_query = st.text_input(
            "Ask the Copilot",
            value=pending or "",
            placeholder='e.g., "Why did retention drop last month?"',
            label_visibility="collapsed",
        )
    with col_btn:
        submit = st.form_submit_button("▶ Ask", use_container_width=True)

if submit and user_query.strip():
    query = user_query.strip()
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.spinner("🔍 Orchestrating agents..."):
        response = st.session_state.supervisor.run(
            query=query,
            time_range=time_range,
            data_products=selected_products or None,
        )

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response.final_summary,
        "response": response,
    })
    st.session_state.last_response = response
    st.rerun()

# Re-render latest response after rerun
if st.session_state.chat_history and st.session_state.last_response:
    render_response(st.session_state.last_response)

# Export last response
if st.session_state.last_response:
    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        export_data = json.dumps(st.session_state.last_response.to_dict(), indent=2)
        st.download_button(
            "⬇ Export Response (JSON)",
            data=export_data,
            file_name=f"copilot_response_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
    with col_exp2:
        if st.button("🗑 Clear History"):
            st.session_state.chat_history = []
            st.session_state.last_response = None
            st.rerun()
