# src/graph/routing.py
# Maps intents to agent node names

INTENT_AGENT_MAP = {
    "full_diagnostic":  [
        "information","knowledge","metadata","capacity"
    ],
    "data_quality":     ["metadata","information"],
    "governance":       ["metadata","knowledge"],
    "incident_review":  ["capacity"],
    "knowledge_lookup": ["knowledge","metadata"],
    "metric_analysis":  ["information","knowledge"],
    "write_ticket":     ["capacity"],
    "write_metadata":   ["metadata"],
    "write_rule":       ["rule"],
    "unknown":          ["information","knowledge"],
}