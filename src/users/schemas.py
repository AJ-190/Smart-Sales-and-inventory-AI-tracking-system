from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional


class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        return value


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None


class UsersOut(BaseModel):
    user_id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class UsersOutUsers(BaseModel):
    business_id: Optional[int] = None
    member_id: Optional[int] = None
    phone: Optional[str] = None
    user_id: Optional[int] = None
    role: str
    name: str
    email: str
    is_verified: bool = False
    created_at: Optional[str] = None

    @field_validator("is_verified", mode="before")
    @classmethod
    def coerce_none_to_false(cls, v):
        return v if v is not None else False

    model_config = ConfigDict(from_attributes=True)


class UserSignUpResponse(BaseModel):
    business_id: Optional[int] = None
    user_id: int
    name: str
    email: str
    role: str
    is_active: bool = True
    is_verified: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class MemberOut(BaseModel):
    member_id: int
    business_id: int
    user_id: int
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_verified: bool = False
    is_active: bool = True

    @field_validator("is_verified", mode="before")
    @classmethod
    def coerce_none_to_false(cls, v):
        return v if v is not None else False

    model_config = ConfigDict(from_attributes=True)
