from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from src.db.database import get_db
from src.auth.utils import verify_token
from src.db.redis import check_jti_blocked
from src.users import models as um



async def get_current_user_ws(
    token: str = Query(...),
    session: AsyncSession = Depends(get_db),
    request: Request = None
):
    token = verify_token(token)

    redis = getattr(request.app.state, "redis", None)
    if redis is None or await check_jti_blocked(redis, token['jti']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = int(token["user"]["sub"])
    user = (await session.execute(
        select(um.Users)
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.Users.user_id == user_id)
    )).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def check_business_membership_ws(
    business_id: int,
    current_user: um.Users = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    membership = (
        await session.execute(
            select(um.BusinessMember)
            .where(
                um.BusinessMember.user_id == current_user.user_id,
                um.BusinessMember.business_id == business_id,
                um.BusinessMember.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this business",
        )
    return current_user

def role_check_ws(allowed_roles: list[um.RoleEnum], is_verified: None  = False):
    async def check(
        current_user = Depends(get_current_user_ws),
        session: AsyncSession = Depends(get_db)
    ):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
        if is_verified and not current_user.is_verified:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not verified")
        return current_user
    return check