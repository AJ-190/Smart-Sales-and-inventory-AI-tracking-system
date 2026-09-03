from pydantic import BaseModel, ConfigDict




class SendNotification(BaseModel):
    title: str
    message: str
    user_id: int
    business_id: int
    notification_type: str

    model_config = ConfigDict(from_attributes=True)
    
    
class ReadNotification(BaseModel):
    notification_id: int
    user_id: int
    message: str
    is_read: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)