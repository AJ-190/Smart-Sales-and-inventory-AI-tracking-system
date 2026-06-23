from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.users import models as um
from src.businesses import models as bm
from src.users import schemas
from src.config import get_settings
from src.auth import utils as auth_utils


async def add_user(post: schemas.UserSignUp, db: AsyncSession):
    result = await db.execute(select(um.Users).where(um.Users.email == post.email))
    existing = result.scalar_one_or_none()
    phone_result = await db.execute(select(um.Users).where(um.Users.phone == post.phone))
    phone_exisiting = phone_result.scalar_one_or_none()

    if existing or phone_exisiting:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already registered")

    role = um.RoleEnum.super_admin if post.email == get_settings().SUPER_ADMIN_EMAIL else um.RoleEnum.user
    user = um.Users(**post.model_dump(exclude={'password'}), password=auth_utils.hash(post.password), role=role)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_users(db: AsyncSession, current_user):
    result = await db.execute(
        select(
            um.BusinessMember.business_id,
            um.BusinessMember.member_id,
            um.Users.user_id,
            um.Users.name,
            um.Users.phone,
            um.Users.email,
            um.Users.role,
            bm.Business.name.label("business_name")
        )
        .join(um.BusinessMember, um.Users.user_id == um.BusinessMember.user_id)
        .join(bm.Business, bm.Business.business_id == um.BusinessMember.business_id)
    )
    users = result.all()

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found in the business")

    return users


async def get_all_users(db: AsyncSession, current_user):
    result = await db.execute(
        select(um.Users.user_id,
               um.Users.name,
               um.Users.email,
               um.Users.role,
               um.Users.phone,
               um.BusinessMember.business_id,
               um.BusinessMember.member_id)
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
    )
    users = result.all()

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found")
    return users


async def get_members(db: AsyncSession, current_user):
    if current_user.role == um.RoleEnum.admin:
        check_result = await db.execute(
            select(um.BusinessMember).where(um.BusinessMember.business_id == current_user.business_id)
        )
        check = check_result.first()
        if not check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not member of any business")

    result = await db.execute(
        select(um.BusinessMember.role,
               um.Users.email,
               um.Users.phone,
               um.Users.name,
               um.BusinessMember.member_id,
               um.BusinessMember.business_id)
        .join(um.Users, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.BusinessMember.business_id == current_user.business_id)
    )
    members = result.all()

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No members found in the business")

    return members


async def get_user(id, db: AsyncSession, current_user):
    result = await db.execute(
        select(um.Users.role,
               um.Users.email,
               um.Users.name,
               um.Users.phone,
               um.Users.user_id,
               um.BusinessMember.member_id,
               um.BusinessMember.business_id)
        .outerjoin(um.BusinessMember,
                   um.BusinessMember.user_id == um.Users.user_id)
        .where(um.Users.user_id == id,
               um.BusinessMember.business_id == current_user.business_id)
    )
    user_ = result.first()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_


async def update_user(id: int, post: schemas.UserUpdate, db: AsyncSession, current_user):
    result = await db.execute(select(um.Users).where(um.Users.user_id == id))
    user_ = result.scalar_one_or_none()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not (current_user.role == um.RoleEnum.super_admin or current_user.user_id == id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unauthorized to perform this action")

    if post.password:
        post.password = auth_utils.hash(post.password)

    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(user_, key, value)

    await db.commit()
    await db.refresh(user_)
    return user_


async def delete_user(id, db: AsyncSession, current_user):
    result = await db.execute(select(um.Users).where(um.Users.user_id == id))
    user_ = result.scalar_one_or_none()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == um.RoleEnum.admin and current_user.business_id != user_.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete users from other businesses")

    await db.delete(user_)
    await db.commit()
    return {"status": "success", "message": "User is deleted successfully"}


async def activate_user(id: int, db: AsyncSession, current_user):
    result = await db.execute(
        select(um.Users, um.BusinessMember.business_id)
        .join(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.Users.user_id == id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user, business_id = row

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user
