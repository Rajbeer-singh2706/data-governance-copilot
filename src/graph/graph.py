"""LangGraph StateGraph definition — sequential routing."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    auto_ticket_node,
    capacity_node,
    information_node,
    knowledge_node,
    metadata_node,
    post_hook,
    pre_hook,
    rule_node,
    supervisor_node,
    synthesizer_node,
)
from src.graph.state import AgentState


def _guardrail_router(state: AgentState) -> str:
    return "supervisor" if state.get("guardrail_passed", True) else "post_hook"


def _agent_router(state: AgentState) -> str:
    """Route to the first agent for the current intent."""
    agents = state.get("next_agents", ["information"])
    first = agents[0] if agents else "information"
    node_map = {
        "information": "information_node",
        "knowledge": "knowledge_node",
        "metadata": "metadata_node",
        "capacity": "capacity_node",
        "rule": "rule_node",
    }
    return node_map.get(first, "information_node")


def _after_first_agent(state: AgentState) -> str:
    """After first agent runs, check if more agents are needed."""
    agents = state.get("next_agents", [])
    ran = state.get("_agents_ran", [])

    remaining = [a for a in agents if a not in ran]
    if not remaining:
        return "auto_ticket"

    node_map = {
        "information": "information_node",
        "knowledge": "knowledge_node",
        "metadata": "metadata_node",
        "capacity": "capacity_node",
        "rule": "rule_node",
    }
    return node_map.get(remaining[0], "auto_ticket")


def build_graph(checkpointer=None):
    """Build and compile the LangGraph StateGraph."""
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("pre_hook", pre_hook)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("information_node", _wrap_agent("information", information_node))
    builder.add_node("knowledge_node", _wrap_agent("knowledge", knowledge_node))
    builder.add_node("metadata_node", _wrap_agent("metadata", metadata_node))
    builder.add_node("capacity_node", _wrap_agent("capacity", capacity_node))
    builder.add_node("rule_node", _wrap_agent("rule", rule_node))
    builder.add_node("auto_ticket", auto_ticket_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("post_hook", post_hook)

    # Edges
    builder.add_edge(START, "pre_hook")
    builder.add_conditional_edges(
        "pre_hook",
        _guardrail_router,
        {"supervisor": "supervisor", "post_hook": "post_hook"},
    )
    builder.add_conditional_edges(
        "supervisor",
        _agent_router,
        {
            "information_node": "information_node",
            "knowledge_node": "knowledge_node",
            "metadata_node": "metadata_node",
            "capacity_node": "capacity_node",
            "rule_node": "rule_node",
        },
    )

    for node in ["information_node", "knowledge_node", "metadata_node",
                 "capacity_node", "rule_node"]:
        builder.add_conditional_edges(
            node,
            _after_first_agent,
            {
                "information_node": "information_node",
                "knowledge_node": "knowledge_node",
                "metadata_node": "metadata_node",
                "capacity_node": "capacity_node",
                "rule_node": "rule_node",
                "auto_ticket": "auto_ticket",
            },
        )

    builder.add_edge("auto_ticket", "synthesizer")
    builder.add_edge("synthesizer", "post_hook")
    builder.add_edge("post_hook", END)

    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    return builder.compile(**kwargs)


def _wrap_agent(name: str, node_fn):
    """Wrap a node to track which agents have run."""
    def wrapped(state: AgentState) -> dict:
        result = node_fn(state)
        ran = list(state.get("_agents_ran", []))
        if name not in ran:
            ran.append(name)
        result["_agents_ran"] = ran
        return result
    wrapped.__name__ = node_fn.__name__
    return wrapped


_graph = None


def get_graph(checkpointer=None):
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer)
    return _graph
