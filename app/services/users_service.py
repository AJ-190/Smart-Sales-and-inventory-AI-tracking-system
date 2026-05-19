
from fastapi import status, HTTPException , Depends
from app import database, models
from app.core import config
from app.core import security
from app import schemas
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.utils import dependencies




def add_user(post: schemas.UserSignUp, db:Session):
    
    existing = db.query(models.Users).filter(models.Users.email == post.email).first()
    phone_exisiting = db.query(models.Users).filter(models.Users.phone == post.phone).first()
    
    if existing or phone_exisiting:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already registered")
    
    role = models.RoleEnum.super_admin if post.email == config.settings.SUPER_ADMIN_EMAIL else models.RoleEnum.user
    user = models.Users(**post.model_dump(exclude={'password'}),password= security.hash(post.password), role=role)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_users(db: Session, current_user):
   
    if current_user.role != models.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    users = (
        db.query(
            models.Users.user_id,
            models.Users.name,
            models.Users.phone,
            models.Users.email,
            models.Business.name.label("business_name")
        )
        .join(models.BusinessMember, models.Users.user_id == models.BusinessMember.user_id)
        .join(models.Business, models.Business.business_id == models.BusinessMember.business_id)
        .group_by(models.Users.user_id, models.Business.name)
        .all()
    )

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found in the business")
    
    return users

def get_all_users(db:Session, current_user):
    if current_user.role != models.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    users = (
        db.query(models.Users.user_id,
                     models.Users.name,
                     models.Users.email,
                     models.Users.role,
                     models.Users.phone,
                     models.BusinessMember.business_id,
                     models.BusinessMember.member_id)
        .outerjoin(models.BusinessMember, models.BusinessMember.user_id == models.Users.user_id)
        .all()
    )
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found")
    return users


def get_members(db: Session, current_user):
    if not current_user.role in [models.RoleEnum.super_admin, models.RoleEnum.admin]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthoirized to perform this action")
    
    if current_user.role == models.RoleEnum.admin:
        check = db.query(models.BusinessMember).filter(models.BusinessMember.business_id == current_user.business_id).first()
        if not check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not member of any business")
        
    members = db.query(models.BusinessMember.role,
                       models.Users.email,
                       models.Users.phone, 
                       models.Users.name, 
                       models.BusinessMember.member_id,
                       models.BusinessMember.business_id).join(
        models.Users, models.BusinessMember.user_id == models.Users.user_id
    ).filter(models.BusinessMember.business_id == current_user.business_id).all()
    
    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No members found in the business")
    
    return members
    
def get_user(id, db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action") 
    user_ = db.query(models.Users.role,
                       models.Users.email, 
                       models.Users.name, 
                       models.Users.phone,
                       models.Users.user_id,
                       models.BusinessMember.member_id,
                       models.BusinessMember.business_id).outerjoin(models.BusinessMember,
                       models.BusinessMember.user_id == models.Users.user_id
                        ).filter(models.Users.user_id == id, models.BusinessMember.business_id == current_user.business_id).first()

    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_
    

def update_user(id: int, post: schemas.UserUpdate, db: Session,current_user):
    user_ = db.query(models.Users).filter(models.Users.user_id == id).first()
    
    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not (current_user.role == models.RoleEnum.super_admin or current_user.user_id == id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unathorized to perform this action")
    
    if post.password:
        post.password = security.hash(post.password)
        
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(user_, key, value)
        
    db.commit()
    db.refresh(user_)
    return user_
        
    
def delete_user(id, db: Session,current_user ):
    
    if current_user.role not in [models.RoleEnum.super_admin, models.RoleEnum.admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    user_ = db.query(models.Users).filter(models.Users.user_id == id).first()
    if not user_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if current_user.role == models.RoleEnum.admin and current_user.business_id != current_user.business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete users from other businesses")
    
    db.delete(user_)
    db.commit()
    return {"status": "success", "message": "User is deleted successfully"}


def activate_user(id: int, db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    # Unpack the tuple
    result = (
        db.query(models.Users, models.BusinessMember.business_id)
        .join(models.BusinessMember, models.BusinessMember.user_id == models.Users.user_id)
        .filter(models.Users.user_id == id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user, business_id = result  

    user.is_active = not user.is_active  
    db.commit()
    db.refresh(user)
    return user

