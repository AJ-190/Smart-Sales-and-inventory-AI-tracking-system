from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class GroupChatMessage(BaseModel):
    business_id: int
    user_id: int
    message: str


class GroupChatMessageResponse(BaseModel):
    id: int
    business_id: int
    user_id: int
    message: str
    is_edited: bool
    is_deleted: bool
    edited_at: Optional[datetime]
    deleted_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WsTicket(BaseModel):
    ticket: str
    expires_in: int