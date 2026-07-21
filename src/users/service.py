from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.users import models as um
from src.businesses import models as bm
from src.users import schemas
from src.config import get_settings
from src.auth import utils as auth_utils
from src.celery_tasks.otp_task import send_otp


async def add_user(post: schemas.UserSignUp, db: AsyncSession):
    existing = (
        await db.execute(
            select(um.Users)
            .where((um.Users.email == post.email) | (um.Users.phone == post.phone))
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already registered")


    user = um.Users(**post.model_dump(exclude={'password'}), password=auth_utils.hash(post.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    try:
        otp = await send_otp(post.email)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("OTP send failed for %s: %s", post.email, e)

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
            um.Users.is_verified,
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
               um.Users.is_verified,
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
        if not current_user.business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not member of any business")
        check_result = await db.execute(
            select(um.BusinessMember).where(um.BusinessMember.business_id == current_user.business_id)
        )
        check = check_result.first()
        if not check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not member of any business")

    if not current_user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business associated with your account")

    result = await db.execute(
        select(um.Users.user_id,
               um.Users.name,
               um.Users.email,
               um.Users.phone,
               um.Users.is_verified,
               um.BusinessMember.member_id,
               um.BusinessMember.business_id,
               um.BusinessMember.role.label("role"))
        .join(um.Users, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.BusinessMember.business_id == current_user.business_id)
    )
    members = result.all()

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No members found in the business")

    return members


async def get_member(member_id: int, db: AsyncSession, current_user):
    if not current_user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business associated with your account")

    result = await db.execute(
        select(um.Users.user_id,
               um.Users.name,
               um.Users.email,
               um.Users.phone,
               um.Users.is_verified,
               um.BusinessMember.member_id,
               um.BusinessMember.business_id,
               um.BusinessMember.role.label("role"),
               um.BusinessMember.is_active)
        .join(um.Users, um.BusinessMember.user_id == um.Users.user_id)
        .where(um.BusinessMember.member_id == member_id)
        .where(um.BusinessMember.business_id == current_user.business_id)
    )
    member = result.first()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    return member


async def get_user(id, db: AsyncSession, current_user):
    stmt = (
        select(um.Users.role,
               um.Users.email,
               um.Users.name,
               um.Users.phone,
               um.Users.user_id,
               um.Users.is_verified,
               um.BusinessMember.member_id,
               um.BusinessMember.business_id)
        .outerjoin(um.BusinessMember,
                   um.BusinessMember.user_id == um.Users.user_id)
        .where(um.Users.user_id == id)
    )
    if current_user.business_id:
        stmt = stmt.where(um.BusinessMember.business_id == current_user.business_id)

    user_ = (await db.execute(stmt)).first()

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

    if current_user.role == um.RoleEnum.admin:
        membership = await db.execute(
            select(um.BusinessMember)
            .where(um.BusinessMember.user_id == id)
            .where(um.BusinessMember.business_id == current_user.business_id)
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete users from other businesses")

    await db.delete(user_)
    await db.commit()
    return {"status": "success", "message": "User is deleted successfully"}


async def activate_user(id: int, db: AsyncSession, current_user):
    result = await db.execute(
        select(um.Users, um.BusinessMember.business_id)
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
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
