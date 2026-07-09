from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from src.config import get_settings
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.users import models as um
import uuid

pwd_context = CryptContext(schemes=['argon2'], deprecated="auto")

def hash(password):
    return pwd_context.hash(password)

def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def AccessToken(user: dict, expire=None, refresh: bool = False):
    payload = {}
    payload["user"] = user
    payload['jti'] = str(uuid.uuid4())
    if expire is None:
        expire_delta = timedelta(minutes=get_settings().ACCESS_TOKEN_TIME)
    elif isinstance(expire, (int, float)):
        expire_delta = timedelta(minutes=expire)
    else:
        expire_delta = expire
    payload['exp'] = datetime.now() + expire_delta
    payload['refresh'] = refresh
    token = jwt.encode(payload, get_settings().SECRET_KEY, algorithm=get_settings().ALGORITHM)
    return token

def verify_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No token provided")

    try:
        return jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_by_id(user_id: int,session: AsyncSession):
    user = (
        await (session.execute(
            select(um.Users)
            .where(um.Users.user_id == user_id)
                               ))
    ).scalar_one_or_none()
    
    return user