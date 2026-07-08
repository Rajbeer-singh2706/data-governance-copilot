"""Teams Pydantic V2 models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


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
    members_added: Optional[List[TeamsUser]] = Field(None, alias="membersAdded")

    @property
    def from_(self) -> Optional[TeamsUser]:
        """Alias for from_user — tests use activity.from_"""
        return self.from_user

    @property
    def membersAdded(self) -> Optional[List[TeamsUser]]:
        """CamelCase alias for members_added."""
        return self.members_added
