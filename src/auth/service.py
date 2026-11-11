import hashlib
import hmac
from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.users import models as um
from src.auth import schemas, utils as auth_utils
from src.config import get_settings
from src.tasks.otp_task import verify_otp


def digest(email: str, otp):
    otp_bytes = f"{email}:{otp}".encode("utf-8")
    return hmac.new(get_settings().SECRET_KEY.encode("utf-8"), otp_bytes, hashlib.sha256).hexdigest()


def _issue_pair(user: um.Users) -> tuple[str, str]:
    claims = {"sub": str(user.user_id), "role": user.role}
    access_token = auth_utils.AccessToken(claims)
    refresh_token = auth_utils.AccessToken(
        claims,
        expire=get_settings().REFRESH_TOKEN_TIME,
        refresh=True,
    )
    return access_token, refresh_token


async def start_session(user: um.Users, db: AsyncSession) -> dict:
    access_token, refresh_token = _issue_pair(user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }


async def login(user_credentials, db: AsyncSession):
    result = await db.execute(
        select(um.Users).where(um.Users.email == user_credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not registered")

    if not auth_utils.verify(user_credentials.password, user.password):
        raise HTTPException(401, "Incorrect password or email")

    return await start_session(user, db)

async def get_user_by_email(email: str, db: AsyncSession):
    user = (await db.execute(select(um.Users).where(um.Users.email == email))).scalar_one_or_none()
    return user


async def refresh(payload: schemas.RefreshRequest, db: AsyncSession):
    if not payload.refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token provided")

    claims = auth_utils.decode_token(payload.refresh_token)

    if not claims.get("refresh"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is required")

    user_id = claims.get("user", {}).get("sub")
    user = (await db.execute(
        select(um.Users).where(um.Users.user_id == int(user_id))
    )).scalar_one_or_none()

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not registered")

    access_token, new_refresh_token = _issue_pair(user)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "Bearer",
    }


async def verify_change_password_otp(current_user, otp: str):
    if not await verify_otp(current_user.email, otp, forgot_pass=False, consume=False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect OTP-Verification Code")

    return {"message": "OTP verified successfully"}


async def change_password(current_user: um.Users, session: AsyncSession, passwords: schemas.Passwords):
    user = (await session.execute(select(um.Users).where(um.Users.user_id == current_user.user_id))).scalar_one_or_none()

    if passwords.new_password.get_secret_value() != passwords.conf_password.get_secret_value():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Passwords do not match")

    if not auth_utils.verify(passwords.old_password.get_secret_value(), user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")

    if not await verify_otp(user.email, passwords.otp, forgot_pass=False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect OTP-Verification Code")


    user.password = auth_utils.hash(passwords.new_password.get_secret_value())
    await session.commit()
    return "Password changed successfully"


async def logout(payload: schemas.LogoutRequest, db: AsyncSession, bearer_token: str | None = None):
    return {"message": "Logged out successfully"}
