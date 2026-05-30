"""Teams Pydantic V2 models."""
from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TeamsUser(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = ""
    name: str = ""
    aad_object_id: Optional[str] = Field(None, alias="aadObjectId")


class TeamsConversation(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = ""
    is_group: Optional[bool] = Field(None, alias="isGroup")
    conversation_type: Optional[str] = Field(None, alias="conversationType")


class TeamsActivity(BaseModel):
    model_config = {"populate_by_name": True}
    type: str = ""
    id: str = ""
    text: Optional[str] = None
    from_user: Optional[TeamsUser] = Field(None, alias="from")
    conversation: Optional[TeamsConversation] = None
    value: Optional[Dict[str, Any]] = None
    service_url: Optional[str] = Field(None, alias="serviceUrl")
    channel_id: Optional[str] = Field(None, alias="channelId")
