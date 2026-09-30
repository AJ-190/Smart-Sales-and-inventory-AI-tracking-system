from pydantic import BaseModel, ConfigDict
from datetime import datetime




class SendNotification(BaseModel):
    title: str
    message: str
    user_id: int
    business_id: int

    model_config = ConfigDict(from_attributes=True)
    
    
class ReadNotification(BaseModel):
    notification_id: int
    user_id: int
    title: str
    message: str
    is_read: bool
    business_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeleteResult(BaseModel):
    """Result of a delete so the client can reconcile without guessing."""

    deleted_id: int
    deleted_count: int = 1


class MarkReadResult(BaseModel):
    updated_count: int
