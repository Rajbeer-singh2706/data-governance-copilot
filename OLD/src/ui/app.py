"""Streamlit chat UI with HITL panel and execution stats."""
from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path when Streamlit executes this file directly.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st
from src.core.logging_utils import get_logger

logger = get_logger("streamlit.app")

st.set_page_config(page_title="Data Governance Copilot", page_icon="🏛️", layout="wide")


def _run_query(query: str, thread_id: str) -> dict:
    logger.info(f"Running query thread_id={thread_id!r} query={query!r}")
    from src.graph.graph import get_graph
    graph = get_graph()
    state = {
        "query": query, "thread_id": thread_id, "user_id": "streamlit-user",
        "time_range": "last_30_days", "data_products": [], "approved": False,
    }
    result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
    logger.info(
        f"Query complete thread_id={thread_id!r} "
        f"confidence={result.get('confidence')} ms={result.get('execution_ms')} "
        f"guardrail_passed={result.get('guardrail_passed', True)}"
    )
    return result


def _render_hitl_panel(pending_action: dict, thread_id: str, query: str):
    st.warning("⚠️ Human Approval Required")
    st.write(pending_action.get("description", "Please review and approve."))
    anomalies = pending_action.get("anomalies", [])
    if anomalies:
        st.write("**Detected Anomalies:**")
        for a in anomalies:
            st.write(f"• {a}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve & Create Tickets", key="approve_btn"):
            from src.graph.graph import get_graph
            graph = get_graph()
            state = {"approved": True, "query": query, "thread_id": thread_id,
                     "data_products": [], "time_range": "last_30_days"}
            result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
            st.success(f"✅ Created {len(result.get('auto_tickets', []))} ticket(s)")
            st.session_state.pop("pending_hitl", None)
            st.rerun()
    with col2:
        if st.button("❌ Reject", key="reject_btn"):
            st.info("Action rejected.")
            st.session_state.pop("pending_hitl", None)
            st.rerun()


def main():
    st.title("🏛️ Data Governance Copilot")
    st.caption("Agentic AI assistant for data quality, governance, and analytics")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        thread_id = st.text_input("Thread ID", value="streamlit-session-1")
        st.divider()
        st.header("📊 Agents")
        for agent in ["information", "knowledge", "metadata", "capacity", "rule"]:
            st.success(f"✅ {agent}")
        import os
        st.divider()
        st.caption(f"Mode: {'🧪 Mock' if os.getenv('ENABLE_MOCK', 'true') == 'true' else '🔗 Live'}")

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("anomalies"):
                with st.expander("⚠️ Anomalies"):
                    for a in msg["anomalies"]:
                        st.warning(a)
            if msg.get("sources"):
                with st.expander("📎 Sources"):
                    for s in msg["sources"]:
                        st.caption(s)
            if msg.get("execution_ms"):
                st.caption(f"⏱ {msg['execution_ms']:.0f}ms | confidence: {msg.get('confidence', 0):.0%}")

    # HITL panel
    if "pending_hitl" in st.session_state:
        _render_hitl_panel(
            st.session_state.pending_hitl["action"],
            st.session_state.pending_hitl["thread_id"],
            st.session_state.pending_hitl["query"],
        )

    # Chat input
    if prompt := st.chat_input("Ask about data quality, governance, metrics..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = _run_query(prompt, thread_id)
                    summary = result.get("final_summary", "Processing complete.")
                    st.write(summary)

                    if result.get("pending_action"):
                        st.session_state.pending_hitl = {
                            "action": result["pending_action"],
                            "thread_id": thread_id,
                            "query": prompt,
                        }
                        st.rerun()

                    msg_data = {
                        "role": "assistant", "content": summary,
                        "anomalies": result.get("anomalies", []),
                        "sources": list(set(result.get("sources", [])))[:5],
                        "execution_ms": result.get("execution_ms", 0),
                        "confidence": result.get("confidence", 0),
                    }
                except Exception as exc:
                    logger.error(f"Query failed thread_id={thread_id!r} query={prompt!r}: {exc}", exc_info=True)
                    msg_data = {"role": "assistant", "content": f"❌ Error: {exc}"}

                st.session_state.messages.append(msg_data)


if __name__ == "__main__":
    main()