import secrets
import hashlib
from datetime import datetime, timezone
from fastapi import status, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from src.users import models as um
from src.auth import schemas, utils as auth_utils
from src.config import get_settings
from src.tasks.otp_task import verify_otp
import hmac
import hashlib

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def verify_token_hash(token: str, hashed_token: str) -> bool:
    return hmac.compare_digest(hash_token(token), hashed_token)


def digest(email: str, otp):
    otp_bytes = f"{email}:{otp}".encode("utf-8")
    return hmac.new(get_settings().SECRET_KEY.encode("utf-8"), otp_bytes, hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_pair(user: um.Users, session_id: str) -> tuple[str, str, datetime]:

    claims = {"sub": str(user.user_id), "role": user.role}
    access_token = auth_utils.AccessToken(claims, sid=session_id)
    refresh_token = auth_utils.AccessToken(
        claims,
        expire=get_settings().REFRESH_TOKEN_TIME,
        refresh=True,
        sid=session_id,
    )
    expires_at = datetime.fromtimestamp(
        auth_utils.decode_token(refresh_token)["exp"], tz=timezone.utc
    )
    return access_token, refresh_token, expires_at


async def _prune_sessions(user_id: int, db: AsyncSession, keep_session_id: str | None = None):
    cap = max(get_settings().MAX_REFRESH_SESSIONS - 1, 0)
    live = select(um.RefreshSession.id).where(
        um.RefreshSession.user_id == user_id,
        um.RefreshSession.revoked_at.is_(None),
    )
    if keep_session_id:
        live = live.where(um.RefreshSession.session_id != keep_session_id)

    overflow = (
        live.order_by(um.RefreshSession.last_used_at.asc().nullsfirst())
        .offset(cap)
        .limit(None)
    )
    doomed = (await db.execute(overflow)).scalars().all()
    if not doomed:
        return

    await db.execute(
        update(um.RefreshSession)
        .where(um.RefreshSession.id.in_(doomed))
        .values(revoked_at=_now())
    )


async def start_session(user: um.Users, db: AsyncSession) -> dict:
    session_id = auth_utils.new_session_id()
    access_token, refresh_token, expires_at = _issue_pair(user, session_id)

    db.add(um.RefreshSession(
        session_id=session_id,
        user_id=user.user_id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
        last_used_at=_now(),
    ))

    user.refresh_token = hash_token(refresh_token)

    await _prune_sessions(user.user_id, db, keep_session_id=session_id)
    await db.commit()

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


async def _find_session(presented: str, claims: dict, db: AsyncSession):
    session_id = claims.get("sid")

    if session_id:
        result = await db.execute(
            select(um.RefreshSession).where(um.RefreshSession.session_id == session_id)
        )
    else:
        result = await db.execute(
            select(um.RefreshSession).where(
                um.RefreshSession.token_hash == hash_token(presented)
            )
        )
    return result.scalar_one_or_none()


def _session_is_dead(session: um.RefreshSession) -> bool:
    if session.revoked_at is not None:
        return True
    expires_at = session.expires_at
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _now()


async def refresh(payload: schemas.RefreshRequest, db: AsyncSession):
    if not payload.refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token provided")

    claims = auth_utils.decode_token(payload.refresh_token)

    if not claims.get("refresh"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is required")

    session = await _find_session(payload.refresh_token, claims, db)

    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    if _session_is_dead(session):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    if not verify_token_hash(payload.refresh_token, session.token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has already been rotated")

    user = (await db.execute(
        select(um.Users).where(um.Users.user_id == session.user_id)
    )).scalar_one_or_none()

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not registered")

    if session.session_id is None:
        session.session_id = auth_utils.new_session_id()

    access_token, new_refresh_token, expires_at = _issue_pair(user, session.session_id)
    session.token_hash = hash_token(new_refresh_token)
    session.expires_at = expires_at
    session.last_used_at = _now()
    user.refresh_token = session.token_hash

    await db.commit()

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
    presented = payload.refresh_token or payload.access_token or bearer_token
    all_sessions = payload.all_sessions

    if not presented:
        return {"message": "Logged out successfully"}

    try:
        claims = auth_utils.decode_token(presented)
    except HTTPException:
        return {"message": "Logged out successfully"}

    user_id = (claims.get("user") or {}).get("sub")
    session_id = claims.get("sid")

    if all_sessions and user_id is not None:
        await db.execute(
            update(um.RefreshSession)
            .where(
                um.RefreshSession.user_id == int(user_id),
                um.RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=_now())
        )
        await db.commit()
        return {"message": "Logged out of all sessions successfully"}

    if session_id:
        sessions = (await db.execute(
            select(um.RefreshSession).where(
                um.RefreshSession.session_id == session_id,
                um.RefreshSession.revoked_at.is_(None),
            )
        )).scalars().all()
    else:
        sessions = (await db.execute(
            select(um.RefreshSession).where(
                um.RefreshSession.token_hash == hash_token(presented),
                um.RefreshSession.revoked_at.is_(None),
            )
        )).scalars().all()

        if not sessions and user_id is not None:
            sessions = (await db.execute(
                select(um.RefreshSession).where(
                    um.RefreshSession.user_id == int(user_id),
                    um.RefreshSession.revoked_at.is_(None),
                )
            )).scalars().all()

    for session in sessions:
        session.revoked_at = _now()
        session.token_hash = secrets.token_hex(32)

    if sessions:
        await db.commit()

    return {"message": "Logged out successfully"}
