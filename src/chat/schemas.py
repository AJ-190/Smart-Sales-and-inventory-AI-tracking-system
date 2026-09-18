from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class GroupChatMessage(BaseModel):
    business_id: int
    user_id: int
    message: str = ""
    attachment_type: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_name: Optional[str] = None
    attachment_size: Optional[int] = None


class GroupChatMessageResponse(BaseModel):
    id: int
    business_id: int
    user_id: int
    message: str
    attachment_type: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_name: Optional[str] = None
    attachment_size: Optional[int] = None
    is_edited: bool
    is_deleted: bool
    edited_at: Optional[datetime]
    deleted_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageOut(GroupChatMessageResponse):
    """Message history + realtime payload shape with sender details."""

    name: Optional[str] = None
    role: Optional[str] = None
    self: bool = False


class ChatHistoryResponse(BaseModel):
    items: list[ChatMessageOut]
    has_more: bool = False
    next_before_id: Optional[int] = None
    total: int = 0


class MessageEdit(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ReadPositionIn(BaseModel):
    last_read_message_id: int


class UnreadCount(BaseModel):
    unread: int


class AttachmentUploadOut(BaseModel):
    attachment_url: str
    attachment_type: str
    attachment_name: str
    attachment_size: int


class WsTicket(BaseModel):
    ticket: str
    expires_in: int