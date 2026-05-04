
from fastapi import status, HTTPException , Depends
from sales_tracker.app.core import config, security
from sales_tracker.app import database, models, schemas
from sqlalchemy.orm import Session
from sqlalchemy import func
from sales_tracker.app.services.users_service import update_user, get_user
from sales_tracker.app.utils import dependencies

def add_business(post, db: Session, current_user):
    existing = (
        db.query(models.Business)
        .filter(models.Business.name == post.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business with the name '{post.name}' is already registered",
        )


    business = models.Business(name=post.name)
    db.add(business)
    db.flush()  

  
    role_update = schemas.UserUpdate.model_validate({"role": models.RoleEnum.admin})
    update_user(current_user.user_id, role_update, db, current_user)


    business_member = models.BusinessMember(
        user_id=current_user.user_id,
        role=models.RoleEnum.admin,  
        business_id=business.business_id,
    )
    db.add(business_member)
    db.commit()

    return business
               
        
def get_businesses(db, current_user):
    
    if current_user.role != models.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    businesses = (
        db.query(
            models.Business,
            func.count(models.BusinessMember.member_id).label("members")
        )
        .outerjoin(models.BusinessMember, models.BusinessMember.business_id == models.Business.business_id)
        .group_by(models.Business.business_id)
        .all()
        )
    
    if not businesses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business registered yet")
    return [{"business": business, "members": members}
            for business, members in businesses]
    
        
                          
                          
def get_business(id, db: Session, current_user):
    if current_user.role != models.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    business_data = (
        db.query(models.Business,
                 func.count(models.BusinessMember.business_id).label("members"))
        .outerjoin(models.BusinessMember, 
                   models.BusinessMember.business_id == models.Business.business_id)
        .filter(models.Business.business_id == id)
        .group_by(models.Business.business_id)
        .first()
    )

    if not business_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"No busines with the id:{id} found")
    business, members = business_data
    return {"business": business, "members": members}

    
def update_business(id, post: schemas.UserSignUp, db:Session, current_user):
    if current_user.role not in [models.RoleEnum.super_admin, models.RoleEnum.admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    business = db.query(models.Business).filter(models.Business == id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(business, key, value)
        
    db.commit()
    db.refresh(business)
    return business

def delete_business(id, db:Session, current_user):

    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this transaction")
    
    business = db.query(models.Business).filter(models.Business.business_id == id).first()
    
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"Business with the ID: {id} not found")
    db.delete(business)
    db.commit()
    return {f"Business with the iD:{id} deleted successfully "}