"""Intent → Agent routing map."""
from __future__ import annotations

from typing import Dict, List

INTENT_AGENT_MAP: Dict[str, List[str]] = {
    "full_diagnostic":  ["information", "knowledge", "metadata", "capacity"],
    "data_quality":     ["metadata", "information"],
    "governance":       ["metadata", "knowledge"],
    "incident_review":  ["capacity"],
    "knowledge_lookup": ["knowledge", "metadata"],
    "metric_analysis":  ["information", "knowledge"],
    "write_ticket":     ["capacity"],
    "write_metadata":   ["metadata"],
    "write_rule":       ["rule"],
    "unknown":          ["information", "knowledge"],
}


def get_agents_for_intent(intent: str) -> List[str]:
    return INTENT_AGENT_MAP.get(intent, INTENT_AGENT_MAP["unknown"])
