from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from graph.state  import AgentState

from graph.nodes  import (
    supervisor_node, information_node, knowledge_node,
    metadata_node, capacity_node, rule_node,
    auto_ticket_node, synthesizer_node,
)

from memory.checkpointer import get_checkpointer

def route_to_agents(state: AgentState):
    """
    Conditional edge: supervisor decides which agents run.
    Returns Send() for each — they run in parallel.
    """
    next_agents = state.get("next_agents", [])

    if not next_agents:
        # No agents — go straight to synthesizer
        return "synthesizer"

    node_map = {
        "information": "information_node",
        "knowledge":   "knowledge_node",
        "metadata":    "metadata_node",
        "capacity":    "capacity_node",
        "rule":        "rule_node",
    }

    # Send() to each agent node simultaneously
    sends = [
        Send(node_map[agent], state)
        for agent in next_agents
        if agent in node_map
    ]

    return sends if sends else "synthesizer"

def build_graph():
    """Assemble and compile the LangGraph StateGraph."""
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("supervisor",       supervisor_node)
    workflow.add_node("information_node", information_node)
    workflow.add_node("knowledge_node",   knowledge_node)
    workflow.add_node("metadata_node",    metadata_node)
    workflow.add_node("capacity_node",    capacity_node)
    workflow.add_node("rule_node",        rule_node)
    workflow.add_node("auto_ticket",      auto_ticket_node)
    workflow.add_node("synthesizer",      synthesizer_node)

    # Entry point
    workflow.add_edge(START, "supervisor")

    # Supervisor → agents (conditional parallel fan-out)
    workflow.add_conditional_edges(
        "supervisor",
        route_to_agents,
        [  # all possible destinations
            "information_node", "knowledge_node",
            "metadata_node",    "capacity_node",
            "rule_node",        "synthesizer",
        ]
    )

    # All agent nodes → auto_ticket → synthesizer → END
    for node in [
        "information_node", "knowledge_node",
        "metadata_node",    "capacity_node",
        "rule_node",
    ]:
        workflow.add_edge(node, "auto_ticket")

    workflow.add_edge("auto_ticket", "synthesizer")
    workflow.add_edge("synthesizer", END)

    # Attach memory checkpointer
    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)

# Singleton — compile once
copilot_graph = build_graph()