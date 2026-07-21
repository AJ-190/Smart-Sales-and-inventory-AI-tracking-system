from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Annotated
from src.users.schemas import UsersOut


class BusinessResponse(BaseModel):
    business_id: int
    name: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class BusinessWithMemberCount(BaseModel):
    business: BusinessResponse
    members: int

    model_config = ConfigDict(from_attributes=True)


class BusinessCreate(BaseModel):
    name: str


class BusinessUpdate(BaseModel):
    name: Optional[str] = None


class Business_Admin(BaseModel):
    password: str


class Business_key(BaseModel):
    business_key: str

    model_config = ConfigDict(from_attributes=True)


class Direction(BaseModel):
    approval_id: int
    dir: Annotated[int, Field(le=1, ge=0)]
    role: Optional[str] = None
    user_id: Optional[int] = None


class ApprovalSend(BaseModel):
    business_key: str
    reason: str
    role: str


class ApprovalsResponseUser(BaseModel):
    business_id: int
    approval_id: int
    requester_id: int
    approval_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ApprovalsResponse(BaseModel):
    approval_id: int
    business_id: int
    reason: str
    approval_type: str
    status: str
    requester: "UsersOut"

    model_config = ConfigDict(from_attributes=True)


class BusinessMemberUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class BusinessMemberResponse(BaseModel):
    member_id: int
    user_id: int
    business_id: int
    role: str
    is_active: bool = True
    joined_at: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
