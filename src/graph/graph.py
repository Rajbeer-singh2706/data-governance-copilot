"""
Day 13: Pre/post hooks wired into the StateGraph.
 
New flow:
  START
    → pre_hook          ← guardrails, PII redaction, timer start
        ↓ (guardrail passed)           ↓ (blocked)
    → supervisor                       ↘
        → [agents in parallel]          → post_hook → END
        → auto_ticket
        → synthesizer
        → post_hook
        → END
 
The conditional edge `route_after_pre_hook` checks guardrail_passed:
  True  → supervisor  (normal path)
  False → post_hook   (short-circuit — final_summary already set by pre_hook)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
 
from graph.state import AgentState
from graph.nodes import (
    pre_hook_node,
    supervisor_node,
    information_node, 
    knowledge_node,
    metadata_node,    
    capacity_node,
    rule_node,
    auto_ticket_node,
    synthesizer_node,
    post_hook_node,
)
from memory.checkpointer import get_checkpointer

# ── Conditional edge: after pre_hook ────────────────────────────────────── 
def route_after_pre_hook(state: AgentState) -> str:
    """
    If guardrails blocked the query, skip all agents and go straight to
    post_hook (which logs the blocked event and computes execution_ms).
    """
    if not state.get("guardrail_passed", True):
        return "post_hook"
    return "supervisor"


# ── Conditional edge: supervisor fan-out ──────────────────────────────────
def route_to_agents(state: AgentState):
    """
    Fan out to one or more agent nodes in parallel using Send().
    Falls back to synthesizer if next_agents is empty.
    """
    next_agents = state.get("next_agents", [])
 
    if not next_agents:
        return "synthesizer"
 
    node_map = {
        "information": "information_node",
        "knowledge":   "knowledge_node",
        "metadata":    "metadata_node",
        "capacity":    "capacity_node",
        "rule":        "rule_node",
    }
 
    sends = [
        Send(node_map[agent], state)
        for agent in next_agents
        if agent in node_map
    ]
 
    return sends if sends else "synthesizer"
 
 
# ── Graph assembly ─────────────────────────────────────────────────────────
def build_graph():
    """Compile the full LangGraph StateGraph with all Day 13 nodes."""
    workflow = StateGraph(AgentState)
 
    # ── Register nodes ───────────────────────────────────────────────────
    workflow.add_node("pre_hook",        pre_hook_node)
    workflow.add_node("supervisor",      supervisor_node)
    workflow.add_node("information_node", information_node)
    workflow.add_node("knowledge_node",  knowledge_node)
    workflow.add_node("metadata_node",   metadata_node)
    workflow.add_node("capacity_node",   capacity_node)
    workflow.add_node("rule_node",       rule_node)
    workflow.add_node("auto_ticket",     auto_ticket_node)
    workflow.add_node("synthesizer",     synthesizer_node)
    workflow.add_node("post_hook",       post_hook_node)
 
    # ── Edges ────────────────────────────────────────────────────────────
    # Entry
    workflow.add_edge(START, "pre_hook")
 
    # pre_hook → supervisor (normal) OR post_hook (guardrail blocked)
    workflow.add_conditional_edges(
        "pre_hook",
        route_after_pre_hook,
        ["supervisor", "post_hook"],
    )
 
    # supervisor → agents (parallel fan-out via Send)
    workflow.add_conditional_edges(
        "supervisor",
        route_to_agents,
        [
            "information_node", "knowledge_node",
            "metadata_node",    "capacity_node",
            "rule_node",        "synthesizer",
        ],
    )
 
    # All agent nodes → auto_ticket
    for node in [
        "information_node", "knowledge_node",
        "metadata_node",    "capacity_node",
        "rule_node",
    ]:
        workflow.add_edge(node, "auto_ticket")
 
    # Linear tail
    workflow.add_edge("auto_ticket",  "synthesizer")
    workflow.add_edge("synthesizer",  "post_hook")
    workflow.add_edge("post_hook",    END)
 
    # Attach SQLite / Postgres checkpointer (persistent memory)
    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)
 
 
# Singleton — compiled once at import time, reused by all callers
copilot_graph = build_graph()