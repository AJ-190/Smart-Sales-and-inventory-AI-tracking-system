from pydantic import BaseModel, EmailStr, validator, SecretStr, field_validator
from typing import Optional


class TokenData(BaseModel):
    id: int


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class Otp_veriification_code(BaseModel):
    otp: str
    email: EmailStr
    password: Optional[SecretStr] = None
    
    @validator("password")
    def validate_password(cls, value):
        if value is None:
            return None

        pw = value.get_secret_value() if isinstance(value, SecretStr) else value
        
        if len(pw) < 8:
            raise ValueError("Password length must be more than 8 characters")
        
        if not any(char.isupper() for char in pw):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not any(char.islower() for char in pw):
            raise ValueError("Password must contain at least on lower case leeter")
        
        if not any(char.isdigit() for char in pw):
            raise ValueError("Password must contain at least one digit")    
        return value
    
class Email(BaseModel):
    email: EmailStr

class OtpCode(BaseModel):
    otp: str
    
class Passwords(BaseModel):
    old_password: SecretStr
    new_password: SecretStr
    conf_password: SecretStr
    otp: str
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value):
        pw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(char.isdigit() for char in pw):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in pw):
            raise ValueError("Password must contain at least one uppercase letter")
        return value