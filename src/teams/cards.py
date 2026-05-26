"""
src/teams/cards.py  — NEW file (Day 17)
Adaptive Card builder functions.
"""
from typing import Dict, List, Optional


def _wrap_card(body: List[Dict], actions: Optional[List[Dict]] = None) -> Dict:
    """Wrap body + actions into a Teams-ready Adaptive Card response."""
    card = {
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


def build_response_card(result: Dict) -> Dict:
    summary, intent = result.get("final_summary",""), result.get("intent","unknown")
    confidence      = result.get("confidence", 0.0)
    anomalies       = result.get("anomalies", [])
    tickets         = result.get("auto_tickets", [])

    body = [
        {"type":"TextBlock","text":"🏛️ Data Governance Copilot",
         "weight":"Bolder","size":"Medium"},
        {"type":"TextBlock","text":f"Intent: **{intent}**  ·  {confidence:.0%}",
         "color":"Accent","size":"Small"},
        {"type":"separator"},
        {"type":"TextBlock","text":summary,"wrap":True},
        {"type":"FactSet","facts":[
            {"title":"Intent","value":intent},
            {"title":"Confidence","value":f"{confidence:.0%}"},
        ]},
    ]
    if anomalies:
        body.append({"type":"separator"})
        body.append({"type":"TextBlock",
            "text":f"⚠️ **{len(anomalies)} Anomaly/Anomalies**",
            "color":"Attention","weight":"Bolder"})
        for a in anomalies:
            body.append({"type":"TextBlock","text":f"• {a}",
                         "color":"Attention","wrap":True,"spacing":"None"})
    if tickets:
        body.append({"type":"separator"})
        body.append({"type":"TextBlock",
            "text":f"🎫 **Tickets Created:** {', '.join(tickets)}",
            "color":"Good","weight":"Bolder"})
    return _wrap_card(body)


def build_hitl_card(pending_action: Dict, thread_id: str, query: str) -> Dict:
    """Card with Approve / Reject Action.Submit buttons."""
    body = [
        {"type":"TextBlock","text":"🔔 Action Required",
         "weight":"Bolder","size":"Medium","color":"Warning"},
        {"type":"TextBlock","text":pending_action.get("message","Approve?"),"wrap":True},
    ]
    for a in pending_action.get("anomalies",[]):
        body.append({"type":"TextBlock","text":f"• {a}","wrap":True,"spacing":"None"})

    actions = [
        {"type":"Action.Submit","title":"✅ Approve — Create Jira Tickets",
         "style":"positive",
         "data":{"action":"approve_tickets","thread_id":thread_id,"query":query}},
        {"type":"Action.Submit","title":"❌ Reject","style":"destructive",
         "data":{"action":"reject_tickets","thread_id":thread_id}},
    ]
    return _wrap_card(body, actions)


def build_error_card(message: str) -> Dict:
    return _wrap_card([
        {"type":"TextBlock","text":"🏛️ Data Governance Copilot","weight":"Bolder"},
        {"type":"TextBlock","text":f"❌ **Error:** {message}",
         "wrap":True,"color":"Attention"},
    ])


def build_welcome_card() -> Dict:
    return _wrap_card([
        {"type":"TextBlock","text":"🏛️ Data Governance Copilot",
         "weight":"Bolder","size":"Large"},
        {"type":"TextBlock",
         "text":"I'm your AI assistant for data governance. Ask me anything.",
         "wrap":True},
        {"type":"FactSet","facts":[
            {"title":"Try asking","value":"Why did retention drop last month?"},
            {"title":"Or","value":"Who owns the bookings dataset?"},
        ]},
    ])