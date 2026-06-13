from fastapi import status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.users import models as um
from src.businesses import models as bm
from src.users import schemas
from src.config import settings
from src.auth import utils as auth_utils


def add_user(post: schemas.UserSignUp, db: Session):
    existing = db.query(um.Users).filter(um.Users.email == post.email).first()
    phone_exisiting = db.query(um.Users).filter(um.Users.phone == post.phone).first()

    if existing or phone_exisiting:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already registered")

    role = um.RoleEnum.super_admin if post.email == settings.SUPER_ADMIN_EMAIL else um.RoleEnum.user
    user = um.Users(**post.model_dump(exclude={'password'}), password=auth_utils.hash(post.password), role=role)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_users(db: Session, current_user):
    if current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    users = (
        db.query(
            um.Users.user_id,
            um.Users.name,
            um.Users.phone,
            um.Users.email,
            bm.Business.name.label("business_name")
        )
        .join(um.BusinessMember, um.Users.user_id == um.BusinessMember.user_id)
        .join(bm.Business, bm.Business.business_id == um.BusinessMember.business_id)
        .group_by(um.Users.user_id, bm.Business.name)
        .all()
    )

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found in the business")

    return users


def get_all_users(db: Session, current_user):
    if current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    users = (
        db.query(um.Users.user_id,
                 um.Users.name,
                 um.Users.email,
                 um.Users.role,
                 um.Users.phone,
                 um.BusinessMember.business_id,
                 um.BusinessMember.member_id)
        .outerjoin(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
        .all()
    )
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found")
    return users


def get_members(db: Session, current_user):
    if current_user.role not in [um.RoleEnum.super_admin, um.RoleEnum.admin]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized to perform this action")

    if current_user.role == um.RoleEnum.admin:
        check = db.query(um.BusinessMember).filter(um.BusinessMember.business_id == current_user.business_id).first()
        if not check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not member of any business")

    members = db.query(um.BusinessMember.role,
                       um.Users.email,
                       um.Users.phone,
                       um.Users.name,
                       um.BusinessMember.member_id,
                       um.BusinessMember.business_id).join(
        um.Users, um.BusinessMember.user_id == um.Users.user_id
    ).filter(um.BusinessMember.business_id == current_user.business_id).all()

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No members found in the business")

    return members


def get_user(id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    user_ = db.query(um.Users.role,
                     um.Users.email,
                     um.Users.name,
                     um.Users.phone,
                     um.Users.user_id,
                     um.BusinessMember.member_id,
                     um.BusinessMember.business_id).outerjoin(um.BusinessMember,
                                                              um.BusinessMember.user_id == um.Users.user_id
                                                              ).filter(um.Users.user_id == id,
                                                                       um.BusinessMember.business_id == current_user.business_id).first()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_


def update_user(id: int, post: schemas.UserUpdate, db: Session, current_user):
    user_ = db.query(um.Users).filter(um.Users.user_id == id).first()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not (current_user.role == um.RoleEnum.super_admin or current_user.user_id == id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unauthorized to perform this action")

    if post.password:
        post.password = auth_utils.hash(post.password)

    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(user_, key, value)

    db.commit()
    db.refresh(user_)
    return user_


def delete_user(id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.super_admin, um.RoleEnum.admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    user_ = db.query(um.Users).filter(um.Users.user_id == id).first()
    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == um.RoleEnum.admin and current_user.business_id != user_.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete users from other businesses")

    db.delete(user_)
    db.commit()
    return {"status": "success", "message": "User is deleted successfully"}


def activate_user(id: int, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    result = (
        db.query(um.Users, um.BusinessMember.business_id)
        .join(um.BusinessMember, um.BusinessMember.user_id == um.Users.user_id)
        .filter(um.Users.user_id == id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user, business_id = result

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user
