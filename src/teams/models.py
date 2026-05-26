"""
src/teams/models.py  — NEW file (Day 17)
Pydantic models for Microsoft Teams Activity payloads.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class TeamsUser(BaseModel):
    id:   str
    name: Optional[str] = "Unknown User"

class TeamsConversation(BaseModel):
    id:              str
    isGroup:         Optional[bool] = False
    conversationType: Optional[str] = None


class TeamsActivity(BaseModel):
    """Incoming payload from Microsoft Teams on every message."""
    type:         str
    id:           Optional[str]               = None
    text:         Optional[str]               = None
    value:        Optional[Dict[str, Any]]    = None   # Action.Submit payload
    from_:        Optional[TeamsUser]         = Field(None, alias="from")
    conversation: Optional[TeamsConversation] = None
    channelId:    Optional[str]               = "msteams"
    serviceUrl:   Optional[str]               = None
    membersAdded: Optional[List[TeamsUser]]   = None

    class Config:
        populate_by_name = True   # accept both "from" and "from_"