from fastapi import status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.users import models as um
from src.users import schemas as users_schema
from src.db.redis import check_jti_blocked
from fastapi import Request


async def valiate_token(request: Request):
    from src.main import app

    token_aata = request.state.user

    redis = app.state.redis
    check_blcoked_jti = await check_jti_blocked(redis, token_aata['jti'])
    if check_blcoked_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Invalid token")
        
    return token_aata

def AccessTokenRequired(token_aata):
    if token_aata.refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Access token is required")

def RefreshTokenRequired(token_data):
    if not token_data.refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                        detail="Refresh token is required")
        
async def get_current_user(token_data = Depends(valiate_token), session: AsyncSession = Depends(get_db)):
    user_id = int(token_data['user']['sub'])
    
    result = await session.execute(
        select(
            um.Users.user_id,
            um.Users.name,
            um.Users.email,
            um.Users.phone,
            um.Users.role,
            um.Users.is_verified,
            um.Users.is_active,
            um.BusinessMember.member_id,
            um.BusinessMember.business_id,
        )
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.Users.user_id == user_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not registered")

    return users_schema.UsersOutUsers(
        user_id=row.user_id,
        name=row.name,
        email=row.email,
        phone=row.phone,
        role=row.role.value if isinstance(row.role, um.RoleEnum) else row.role,
        is_verified=row.is_verified,
        member_id=row.member_id,
        business_id=row.business_id,
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
