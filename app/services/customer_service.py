
from fastapi import HTTPException, status, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app import models, schemas




def check_current_user_business(db: Session, current_user: models.Users, business_id: int):
    business = (
        db.query(models.BusinessMember)
        .filter(models.BusinessMember.user_id == current_user.user_id)
        .filter(models.BusinessMember.business_id == business_id)
        .first()
    )
    
    if not business:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
def create_customer(db: Session, current_user: models.Users, customer: schemas.CustomerCreate, business_id: int):
    if  current_user.role not in [
       models.RoleEnum.admin, 
       models.RoleEnum.super_admin, 
       models.RoleEnum.manager,
       models.RoleEnum.cashier
]:
       raise HTTPException(
           status_code=status.HTTP_401_UNAUTHORIZED, 
           detail="Unauthorized to perform this action")
       

    check_current_user_business(db, current_user, business_id)
    check_customer_exist = (
        db.query(models.Customer)
        .filter(models.Customer.email == customer.email)
        .filter(models.Customer.business_id == business_id)
        .first()
    )

    if check_customer_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer already exist")

    user = models.Customer(**customer.model_dump(), business_id=business_id)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



def get_customers(business_id, db: Session, current_user, search, skip, limit):
    if current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin,
        models.RoleEnum.manager,
        models.RoleEnum.cashier
    ]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized to perform this action"
        )
    
    check_current_user_business(db, current_user, business_id)
    base_query = (
        db.query(models.Customer)
        .filter(models.Customer.business_id == business_id)
        
    )
    
    if search: 
        search_query = f"%{search}%"
        base_query = (
            base_query.filter(
                or_(
                    models.Customer.name .ilike(search_query),
                    models.Customer.email.ilike(search_query),
                    models.Customer.phone.ilike(search_query)
                )
            )
        )
    customers =  base_query.order_by(models.Customer.created_at.desc()).limit(limit).offset(skip).all()
    if not customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customers found"
        )
    return customers


