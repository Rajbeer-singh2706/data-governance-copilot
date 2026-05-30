"""Adaptive Card builders for Teams bot."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_response_card(result: Dict) -> Dict:
    summary = result.get("final_summary", result.get("summary", "No summary available."))
    anomalies = result.get("anomalies", [])
    confidence = result.get("confidence", 0.0)

    body = [
        {"type": "TextBlock", "text": "📊 Data Governance Copilot", "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": summary, "wrap": True},
        {"type": "TextBlock", "text": f"Confidence: {confidence:.0%}", "isSubtle": True},
    ]
    if anomalies:
        body.append({"type": "TextBlock", "text": "⚠️ Anomalies Detected:", "weight": "Bolder"})
        for a in anomalies[:5]:
            body.append({"type": "TextBlock", "text": f"• {a}", "wrap": True, "color": "Warning"})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": body}


def build_hitl_card(pending_action: Dict, thread_id: str, query: str) -> Dict:
    description = pending_action.get("description", "Approve this action?")
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🔔 Action Required", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": description, "wrap": True},
            {"type": "TextBlock", "text": f"Query: {query}", "isSubtle": True, "wrap": True},
        ],
        "actions": [
            {"type": "Action.Submit", "title": "✅ Approve",
             "data": {"action": "approve", "thread_id": thread_id}},
            {"type": "Action.Submit", "title": "❌ Reject",
             "data": {"action": "reject", "thread_id": thread_id}},
        ],
    }


def build_error_card(message: str) -> Dict:
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "❌ Error", "weight": "Bolder", "color": "Attention"},
            {"type": "TextBlock", "text": message, "wrap": True},
        ],
    }


def build_welcome_card() -> Dict:
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "👋 Data Governance Copilot", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": "Ask me about data quality, governance policies, metrics, or incidents.", "wrap": True},
        ],
    }


def build_thinking_card() -> Dict:
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": "⏳ Processing your request...", "isSubtle": True}],
    }
