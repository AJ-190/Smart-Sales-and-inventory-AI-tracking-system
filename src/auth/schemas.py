from pydantic import BaseModel, EmailStr
from typing import Optional


class TokenData(BaseModel):
    id: int


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class Otp_veriification_code(BaseModel):
    otp: str
    email: Optional[EmailStr] = None
    
class Email(BaseModel):
    email: EmailStr
    
