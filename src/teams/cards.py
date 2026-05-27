"""
src/teams/cards.py
Day 17: Adaptive Card builder functions.

Each function returns a dict that Teams renders as a rich card.
Cards are returned inside a TeamsResponse as an attachment.

Card types:
  build_response_card()  — main answer card with facts + anomalies + tickets
  build_hitl_card()      — approval card with Approve / Reject buttons
  build_error_card()     — error display card
  build_welcome_card()   — shown when bot is added to a channel
  build_thinking_card()  — "processing" placeholder (sent immediately, updated)
"""
from __future__ import annotations

from typing import Dict, List, Optional


# ── Internal helpers ───────────────────────────────────────────────────────

def _wrap_card(body: List[Dict], actions: Optional[List[Dict]] = None) -> Dict:
    """Wrap body + actions into a complete Adaptive Card attachment dict."""
    card: Dict = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type":    "AdaptiveCard",
        "version": "1.4",
        "body":    body,
    }
    if actions:
        card["actions"] = actions

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content":     card,
        }],
    }


# ── Main response card ─────────────────────────────────────────────────────

def build_response_card(result: Dict) -> Dict:
    """
    Build the primary answer card from a LangGraph result dict.

    Sections (in order):
      1. Header — copilot title + intent badge
      2. Summary — the GPT-4o synthesised answer
      3. Fact set — intent, confidence, execution time, agents used
      4. Anomaly block — ⚠️ warning list (if anomalies found)
      5. Ticket block — 🎫 created ticket IDs (if tickets created)
      6. Error block — ⚠️ agent errors (if any)
    """
    summary       = result.get("final_summary", "No results found.")
    intent        = result.get("intent", "unknown")
    confidence    = result.get("confidence", 0.0)
    execution_ms  = result.get("execution_ms", 0.0)
    anomalies     = result.get("anomalies", [])
    tickets       = result.get("auto_tickets", [])
    errors        = result.get("errors", [])
    agent_results = result.get("agent_results", [])
    agents_used   = [r.get("agent","") for r in agent_results if r.get("agent")]

    body: List[Dict] = []

    # ── Header ─────────────────────────────────────────────────────────
    body.append({
        "type":    "TextBlock",
        "text":    "🏛️ Data Governance Copilot",
        "weight":  "Bolder",
        "size":    "Medium",
        "spacing": "None",
    })
    body.append({
        "type":  "TextBlock",
        "text":  f"Intent: **{intent}**  ·  Confidence: **{confidence:.0%}**",
        "size":  "Small",
        "color": "Accent",
        "spacing": "None",
    })

    # ── Summary ────────────────────────────────────────────────────────
    body.append({"type": "separator"})
    body.append({
        "type": "TextBlock",
        "text": summary,
        "wrap": True,
    })

    # ── Fact set ───────────────────────────────────────────────────────
    facts = [
        {"title": "Intent",    "value": intent},
        {"title": "Confidence","value": f"{confidence:.0%}"},
        {"title": "Exec time", "value": f"{execution_ms:.0f} ms"},
    ]
    if agents_used:
        facts.append({"title": "Agents", "value": ", ".join(agents_used)})

    body.append({"type": "FactSet", "facts": facts, "spacing": "Small"})

    # ── Anomalies ──────────────────────────────────────────────────────
    if anomalies:
        body.append({"type": "separator"})
        body.append({
            "type":   "TextBlock",
            "text":   f"⚠️ **{len(anomalies)} Anomaly/Anomalies Detected**",
            "weight": "Bolder",
            "color":  "Attention",
        })
        for a in anomalies:
            body.append({
                "type":  "TextBlock",
                "text":  f"• {a}",
                "wrap":  True,
                "color": "Attention",
                "spacing": "None",
            })

    # ── Auto-tickets ───────────────────────────────────────────────────
    if tickets:
        body.append({"type": "separator"})
        body.append({
            "type":   "TextBlock",
            "text":   f"🎫 **Jira Tickets Created:** {', '.join(tickets)}",
            "weight": "Bolder",
            "color":  "Good",
        })

    # ── Agent errors ───────────────────────────────────────────────────
    if errors:
        body.append({"type": "separator"})
        body.append({
            "type":  "TextBlock",
            "text":  f"⚠️ {len(errors)} agent(s) had errors — partial results shown.",
            "wrap":  True,
            "color": "Warning",
            "size":  "Small",
        })

    return _wrap_card(body)


# ── HITL approval card ─────────────────────────────────────────────────────

def build_hitl_card(pending_action: Dict, thread_id: str, query: str) -> Dict:
    """
    Card with Approve / Reject buttons for Human-in-the-Loop ticket creation.

    When user clicks Approve, Teams sends an invoke Activity back to the
    webhook with value = {"action": "approve_tickets", "thread_id": "...",
    "query": "..."}.
    """
    anomalies = pending_action.get("anomalies", [])
    products  = pending_action.get("products", [])
    count     = pending_action.get("count", len(anomalies))
    message   = pending_action.get("message", "Approval required.")

    body: List[Dict] = [
        {
            "type":   "TextBlock",
            "text":   "🔔 Action Required",
            "weight": "Bolder",
            "size":   "Medium",
            "color":  "Warning",
        },
        {
            "type": "TextBlock",
            "text": message,
            "wrap": True,
        },
    ]

    if anomalies:
        body.append({
            "type":  "TextBlock",
            "text":  f"**{count} critical anomaly/anomalies:**",
            "weight": "Bolder",
        })
        for a in anomalies:
            body.append({
                "type": "TextBlock",
                "text": f"• {a}",
                "wrap": True,
                "spacing": "None",
            })

    if products:
        body.append({
            "type":  "FactSet",
            "facts": [{"title": "Data products", "value": ", ".join(products)}],
        })

    actions = [
        {
            "type":  "Action.Submit",
            "title": "✅ Approve — Create Jira Tickets",
            "style": "positive",
            "data":  {
                "action":    "approve_tickets",
                "thread_id": thread_id,
                "query":     query,
            },
        },
        {
            "type":  "Action.Submit",
            "title": "❌ Reject",
            "style": "destructive",
            "data":  {
                "action":    "reject_tickets",
                "thread_id": thread_id,
            },
        },
    ]

    return _wrap_card(body, actions)


# ── Utility cards ──────────────────────────────────────────────────────────

def build_error_card(message: str) -> Dict:
    """Simple error display card."""
    return _wrap_card([
        {
            "type":   "TextBlock",
            "text":   "🏛️ Data Governance Copilot",
            "weight": "Bolder",
            "size":   "Medium",
        },
        {
            "type":  "TextBlock",
            "text":  f"❌ **Error:** {message}",
            "wrap":  True,
            "color": "Attention",
        },
    ])


def build_welcome_card() -> Dict:
    """Card shown when the bot is first added to a channel."""
    return _wrap_card([
        {
            "type":   "TextBlock",
            "text":   "🏛️ Data Governance Copilot",
            "weight": "Bolder",
            "size":   "Large",
        },
        {
            "type": "TextBlock",
            "text": "I'm your AI assistant for data governance and analytics. Ask me anything about your data products.",
            "wrap": True,
        },
        {
            "type":  "FactSet",
            "facts": [
                {"title": "Try asking", "value": "Why did retention drop last month?"},
                {"title": "Or",        "value": "Who owns the bookings dataset?"},
                {"title": "Or",        "value": "Show open Jira bugs for retention"},
            ],
        },
    ])


def build_thinking_card() -> Dict:
    """Immediate acknowledgement card sent while the graph runs."""
    return _wrap_card([
        {
            "type":   "TextBlock",
            "text":   "🏛️ Data Governance Copilot",
            "weight": "Bolder",
        },
        {
            "type":  "TextBlock",
            "text":  "🔍 Analysing your query across all data agents...",
            "color": "Accent",
            "wrap":  True,
        },
    ])