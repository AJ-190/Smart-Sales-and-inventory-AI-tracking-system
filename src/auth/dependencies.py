from fastapi.security import OAuth2PasswordBearer
from fastapi import status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.auth import utils as auth_utils
from src.users import models as um
from src.users import schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    payload = auth_utils.verify_token(token)
    user_id = int(payload.get("sub"))

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    result = await db.execute(
        select(
            um.Users.user_id,
            um.Users.name,
            um.Users.email,
            um.BusinessMember.member_id,
            um.BusinessMember.business_id,
            um.Users.role
        )
        .outerjoin(um.BusinessMember, um.Users.user_id == um.BusinessMember.user_id)
        .where(um.Users.user_id == user_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return schemas.UsersOutUsers(
        user_id=row.user_id,
        name=row.name,
        email=row.email,
        member_id=row.member_id,
        business_id=row.business_id,
        role=row.role
    )


def role_checker(allowed_roles: list[um.RoleEnum]):
    async def check(current_user: schemas.UsersOutUsers = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized to perform this action"
            )
        return current_user
    return check
