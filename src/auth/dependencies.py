from datetime import datetime, timezone

from fastapi import status, HTTPException, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, and_
from src.db.database import get_db
from src.users import models as um
from src.users import schemas as users_schema
from src.db.redis import check_jti_blocked
from src.auth.utils import verify_token
from src.config import get_settings


from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()


def bearer_credential(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


async def validate_token(request:  Request, creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = creds.credentials

    token_data = verify_token(token)

    redis = request.app.state.redis
    if await check_jti_blocked(redis, token_data["jti"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return token_data


async def AccessTokenRequired(token_data=Depends(validate_token)):
    if token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is required",
        )
    return token_data


async def RefreshTokenRequired(token_data=Depends(validate_token)):
    if not token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )
    return token_data


async def ensure_session_alive(token_data: dict, session: AsyncSession):
    session_id = token_data.get("sid")
    if not session_id:
        return

    row = (
        await session.execute(
            select(um.RefreshSession.revoked_at, um.RefreshSession.expires_at)
            .where(um.RefreshSession.session_id == session_id)
        )
    ).first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
        )

    revoked_at, expires_at = row
    if revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
        )

    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
            )


async def get_current_user(
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    await ensure_session_alive(token_data, session)

    try:
        user_id = int(token_data["user"]["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    result = await session.execute(
        select(
            um.Users.user_id,
            um.Users.name,
            um.Users.email,
            um.Users.phone,
            um.Users.role.label("user_role"),
            um.BusinessMember.role,
            um.Users.is_verified,
            um.Users.is_active,
            um.Users.created_at,
            um.BusinessMember.member_id,
            um.BusinessMember.business_id,
        )
        .outerjoin(
            um.BusinessMember,
            and_(
                um.BusinessMember.user_id == um.Users.user_id,
                um.ACTIVE_MEMBERSHIP,
            ),
        )
        .where(um.Users.user_id == user_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not registered",
        )

    if row.email == get_settings().SUPER_ADMIN_EMAIL:
        effective_role = um.RoleEnum.super_admin.value
    elif row.user_role == um.RoleEnum.super_admin:
        effective_role = um.RoleEnum.super_admin.value
    elif row.role is not None:
        effective_role = row.role.value if isinstance(row.role, um.RoleEnum) else row.role
    else:
        effective_role = row.user_role.value if isinstance(row.user_role, um.RoleEnum) else str(row.user_role)

    return users_schema.UsersOutUsers(
        user_id=row.user_id,
        name=row.name,
        email=row.email,
        phone=row.phone,
        role=effective_role,
        is_verified=row.is_verified,
        member_id=row.member_id,
        business_id=row.business_id,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


def get_my_profile(current_user: users_schema.UsersOutUsers = Depends(get_current_user)):
    return current_user


def role_checker(allowed_roles: list[um.RoleEnum], require_verified: bool = False):
    async def check(
        current_user: users_schema.UsersOutUsers = Depends(get_current_user),
    ):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to perform this action",
            )
        if require_verified and not current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account not verified",
            )
        return current_user

    return check
