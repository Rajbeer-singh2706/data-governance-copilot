"""Adaptive Card builders for Teams bot."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _teams_message(card_content: Dict) -> Dict:
    """Wrap an AdaptiveCard in a Teams message envelope."""
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content,
            }
        ],
    }


def _adaptive_card(body: List, actions: List = None) -> Dict:
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return card


def build_response_card(result: Dict) -> Dict:
    summary = result.get("final_summary", result.get("summary", "No summary available."))
    anomalies = result.get("anomalies", [])
    confidence = result.get("confidence", 0.0)
    auto_tickets = result.get("auto_tickets", [])
    errors = result.get("errors", [])

    body = [
        {"type": "TextBlock", "text": "📊 Data Governance Copilot",
         "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": summary, "wrap": True},
        {"type": "TextBlock", "text": f"Confidence: {confidence:.0%}", "isSubtle": True},
    ]
    if anomalies:
        body.append({"type": "TextBlock", "text": "⚠️ Anomaly Detected:", "weight": "Bolder"})
        for a in anomalies[:5]:
            body.append({"type": "TextBlock", "text": f"• {a}", "wrap": True, "color": "Warning"})
    if auto_tickets:
        body.append({"type": "TextBlock", "text": "🎫 Tickets:", "weight": "Bolder"})
        for t in auto_tickets[:5]:
            body.append({"type": "TextBlock", "text": f"• {t}", "wrap": True})
    if errors:
        body.append({"type": "TextBlock", "text": "❌ Errors:", "weight": "Bolder",
                     "color": "Attention"})
        for e in errors[:3]:
            err_text = e.get("error", str(e)) if isinstance(e, dict) else str(e)
            body.append({"type": "TextBlock", "text": f"• {err_text}", "wrap": True})

    return _teams_message(_adaptive_card(body))


def build_hitl_card(pending_action: Dict, thread_id: str, query: str) -> Dict:
    description = pending_action.get("message", pending_action.get("description",
                                                                    "Approve this action?"))
    anomalies = pending_action.get("anomalies", [])

    body = [
        {"type": "TextBlock", "text": "🔔 Action Required",
         "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": description, "wrap": True},
        {"type": "TextBlock", "text": f"Query: {query}", "isSubtle": True, "wrap": True},
    ]
    for a in anomalies[:3]:
        body.append({"type": "TextBlock", "text": f"• {a}", "wrap": True, "color": "Warning"})

    actions = [
        {"type": "Action.Submit", "title": "✅ Approve",
         "data": {"action": "approve_tickets", "thread_id": thread_id, "query": query}},
        {"type": "Action.Submit", "title": "❌ Reject",
         "data": {"action": "reject_tickets", "thread_id": thread_id, "query": query}},
    ]
    return _teams_message(_adaptive_card(body, actions))


def build_error_card(message: str) -> Dict:
    body = [
        {"type": "TextBlock", "text": "❌ Error", "weight": "Bolder", "color": "Attention"},
        {"type": "TextBlock", "text": message, "wrap": True},
    ]
    return _teams_message(_adaptive_card(body))


def build_welcome_card() -> Dict:
    body = [
        {"type": "TextBlock", "text": "👋 Data Governance Copilot",
         "weight": "Bolder", "size": "Large"},
        {"type": "TextBlock",
         "text": "Ask me about data quality, metrics, governance policies, or incidents.",
         "wrap": True},
    ]
    return _teams_message(_adaptive_card(body))


def build_thinking_card() -> Dict:
    body = [
        {"type": "TextBlock", "text": "🔍 Analysing your request…", "wrap": True},
    ]
    return _teams_message(_adaptive_card(body))
