from pydantic import BaseModel, EmailStr, SecretStr, field_validator
from typing import Optional


class TokenData(BaseModel):
    id: int


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


def _validate_otp(value):
    if not isinstance(value, str) or not value.isdigit() or len(value) != 6:
        raise ValueError("OTP must be exactly 6 digits")
    return value

class OtpVerificationCode(BaseModel):
    otp: str
    email: EmailStr
    password: Optional[SecretStr] = None

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value):
        return _validate_otp(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if value is None:
            return None

        pw = value.get_secret_value() if isinstance(value, SecretStr) else value

        if len(pw) < 8:
            raise ValueError("Password length must be more than 8 characters")

        if not any(char.isupper() for char in pw):
            raise ValueError("Password must contain at least one uppercase letter")

        if not any(char.islower() for char in pw):
            raise ValueError("Password must contain at least one lowercase letter")

        if not any(char.isdigit() for char in pw):
            raise ValueError("Password must contain at least one digit")
        return value

class Email(BaseModel):
    email: EmailStr

class OtpCode(BaseModel):
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value):
        return _validate_otp(value)

class PasswordVerify(BaseModel):
    password: SecretStr

class Passwords(BaseModel):
    old_password: SecretStr
    new_password: SecretStr
    conf_password: SecretStr
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value):
        return _validate_otp(value)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value):
        pw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if len(pw) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(char.isdigit() for char in pw):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in pw):
            raise ValueError("Password must contain at least one uppercase letter")
        return value