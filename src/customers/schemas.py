from typing import Optional
from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    customer_id: int
    business_id: int
    name: str
    phone: str
    email: str
    address: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
