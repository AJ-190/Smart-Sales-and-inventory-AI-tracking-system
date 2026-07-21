from fastapi import status, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.users import models as um
from src.users import schemas as users_schema
from src.db.redis import check_jti_blocked
from src.auth.utils import verify_token
from src.config import get_settings


async def valiate_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ")[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(token)

    redis = request.app.state.redis
    if await check_jti_blocked(redis, token_data["jti"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return token_data


async def AccessTokenRequired(token_data=Depends(valiate_token)):
    if token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is required",
        )
    return token_data


async def RefreshTokenRequired(token_data=Depends(valiate_token)):
    if not token_data.get("refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )
    return token_data


async def get_current_user(
    token_data=Depends(valiate_token),
    session: AsyncSession = Depends(get_db),
):
    user_id = int(token_data["user"]["sub"])

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
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
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
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized to perform this action",
            )
        if require_verified and not current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account not verified",
            )
        return current_user

    return check
