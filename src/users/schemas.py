from pydantic import BaseModel, EmailStr, ConfigDict, computed_field, field_validator
from typing import Optional
from datetime import datetime

CURRENCY_BY_COUNTRY = {
    "GH": "GHS",
    "NG": "NGN",
    "KE": "KES",
    "UG": "UGX",
    "TZ": "TZS",
    "ZA": "ZAR",
    "US": "USD",
    "GB": "GBP",
}


def _clean_country_code(value):
    if isinstance(value, str) and value.strip():
        return value.strip().upper()[:2]
    return "GH"


class UserSignUp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: EmailStr
    password: str
    phone: str
    country_code: str = "GH"

    @field_validator("country_code", mode="before")
    @classmethod
    def normalize_country_code(cls, value):
        return _clean_country_code(value)

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

    @field_validator("email")
    @classmethod
    def validate_email(cls, email):
        if "@" not in email:
            raise ValueError("Email must contain '@'")
        if not email.split("@")[-1] or "." not in email.split("@")[-1]:
            raise ValueError("Email domain is invalid")
        return email


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    country_code: Optional[str] = None

    @field_validator("country_code", mode="before")
    @classmethod
    def normalize_country_code(cls, value):
        return _clean_country_code(value) if value is not None else None


class UsersOut(BaseModel):
    user_id: int
    name: str
    email: str
    country_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UsersOutUsers(BaseModel):
    business_id: Optional[int] = None
    member_id: Optional[int] = None
    phone: Optional[str] = None
    user_id: Optional[int] = None
    role: str
    name: str
    email: str
    country_code: Optional[str] = None
    is_verified: bool = False
    created_at: Optional[datetime] = None

    @computed_field
    @property
    def currency(self) -> str:
        return CURRENCY_BY_COUNTRY.get((self.country_code or "").upper(), "GHS")

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
    country_code: Optional[str] = None
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
    country_code: Optional[str] = None
    role: str
    is_verified: bool = False
    is_active: bool = True

    @field_validator("is_verified", mode="before")
    @classmethod
    def coerce_none_to_false(cls, v):
        return v if v is not None else False

    model_config = ConfigDict(from_attributes=True)
