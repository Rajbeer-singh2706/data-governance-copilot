"""
src/teams/models.py
Day 17: Pydantic models for Microsoft Teams Activity payloads.

Teams sends an Activity JSON to our webhook on every message.
We parse it, run the query, and respond with a TeamsResponse
wrapping an Adaptive Card.

Activity types we handle:
  message            — user sends a text message
  invoke             — user clicks an Adaptive Card action button
  conversationUpdate — bot added/removed from a channel
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Incoming from Teams ────────────────────────────────────────────────────

class TeamsUser(BaseModel):
    """The sender of an Activity (user or bot)."""
    id:   str
    name: Optional[str] = "Unknown User"


class TeamsConversation(BaseModel):
    """The conversation (channel / 1:1 chat) context."""
    id:              str
    isGroup:         Optional[bool] = False
    conversationType: Optional[str] = None
    name:            Optional[str]  = None


class TeamsChannelData(BaseModel):
    """Teams-specific metadata attached to Activities."""
    tenant: Optional[Dict[str, Any]] = None
    team:   Optional[Dict[str, Any]] = None


class TeamsActivity(BaseModel):
    """
    Incoming payload from Microsoft Teams.

    Key fields:
      type         — "message" | "invoke" | "conversationUpdate"
      text         — user's message text (present when type == "message")
      value        — action payload (present when type == "invoke",
                     i.e. when user clicks an Adaptive Card button)
      from_        — sender (aliased from "from" to avoid Python keyword conflict)
      conversation — conversation context (used to reply back)
    """
    type:         str
    id:           Optional[str]              = None
    timestamp:    Optional[str]              = None
    text:         Optional[str]              = None
    value:        Optional[Dict[str, Any]]   = None   # action button payload
    from_:        Optional[TeamsUser]        = Field(None, alias="from")
    conversation: Optional[TeamsConversation] = None
    channelId:    Optional[str]              = "msteams"
    serviceUrl:   Optional[str]              = None
    channelData:  Optional[TeamsChannelData] = None
    membersAdded: Optional[List[TeamsUser]]  = None   # conversationUpdate

    model_config = {"populate_by_name": True}  # allow both "from" and "from_"


# ── Adaptive Card building blocks ──────────────────────────────────────────

class AdaptiveCardBody(BaseModel):
    """A single body element inside an Adaptive Card."""
    type:   str
    text:   Optional[str]             = None
    weight: Optional[str]             = None
    size:   Optional[str]             = None
    color:  Optional[str]             = None
    wrap:   Optional[bool]            = True
    facts:  Optional[List[Dict]]      = None
    actions: Optional[List[Dict]]     = None


class AdaptiveCard(BaseModel):
    schema_:  str        = Field("http://adaptivecards.io/schemas/adaptive-card.json",
                                  alias="$schema")
    type:     str        = "AdaptiveCard"
    version:  str        = "1.4"
    body:     List[Dict] = []
    actions:  List[Dict] = []

    model_config = {"populate_by_name": True}


# ── Outgoing to Teams ──────────────────────────────────────────────────────

class TeamsAttachment(BaseModel):
    contentType: str  = "application/vnd.microsoft.card.adaptive"
    content:     Dict = {}


class TeamsResponse(BaseModel):
    """The JSON body we POST back to Teams as a reply."""
    type:        str                  = "message"
    attachments: List[TeamsAttachment] = []