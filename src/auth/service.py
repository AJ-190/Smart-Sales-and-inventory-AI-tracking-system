import secrets
import hashlib
from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.users import models as um
from src.auth import schemas, utils as auth_utils
from src.config import get_settings

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def verify_token_hash(token: str, hashed_token: str) -> bool:
    return hash_token(token) == hashed_token

async def login(user_credentials, db: AsyncSession):
    result = await db.execute(
        select(um.Users).where(um.Users.email == user_credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not registered")

    if not auth_utils.verify(user_credentials.password, user.password):
        raise HTTPException(401, "Incorrect password or email")
    
    access_token = auth_utils.AccessToken({"sub": str(user.user_id), "role": user.role})
    refresh_token = auth_utils.AccessToken( {"sub": str(user.user_id), "role": user.role}, expire=get_settings().REFRESH_TOKEN_TIME, refresh=True)

    user.refresh_token = hash_token(refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }

async def get_user_by_email(email: str, db: AsyncSession):
    user = (await db.execute(select(um.Users).where(um.Users.email == email))).scalar_one_or_none()
    return user

async def refresh(payload: schemas.Token, db: AsyncSession):
    token_hash = hash_token(payload.refresh_token)

    result = await db.execute(
        select(um.Users).where(um.Users.refresh_token == token_hash)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(403, "Invalid or expired refresh token")
    
    new_access_token = auth_utils.AccessToken({"sub": str(user.user_id), "role": user.role})
    new_refresh_token = auth_utils.AccessToken( {"sub": str(user.user_id), "role": user.role}, expire=get_settings().REFRESH_TOKEN_TIME, refresh=True)


    user.refresh_token = hash_token(new_refresh_token)
    await db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "Bearer"
    }

async def logout(payload: schemas.Token, db: AsyncSession):
    token_hash = hash_token(payload.refresh_token)

    result = await db.execute(
        select(um.Users).where(um.Users.refresh_token == token_hash)
    )
    user = result.scalar_one_or_none()

    if user:
        user.refresh_token = None
        await db.commit()

    return {"message": "Logged out successfully"}
