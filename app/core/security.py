from passlib.context import CryptContext
from datetime import datetime, timezone, timedelta
from app.core.config import settings
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import status, HTTPException

pwd_context = CryptContext(schemes=['argon2'], deprecated="auto")

def hash(password):
    return pwd_context.hash(password)

def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_TIME)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def refresh_token(data: dict):
    to_code = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TIME)
    to_code.update({"exp": expire})
    token = jwt.encode(to_code, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def verify_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )