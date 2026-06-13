from fastapi import status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.customers import models as cm
from src.customers import schemas
from src.users import models as um


def role_permission_check(current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager,
        um.RoleEnum.cashier
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unauthorized to perform this action")


def check_current_user_business(db: Session, current_user, business_id: int):
    business = (
        db.query(um.BusinessMember)
        .filter(um.BusinessMember.user_id == current_user.user_id)
        .filter(um.BusinessMember.business_id == business_id)
        .first()
    )

    if not business:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")


def create_customer(db: Session, current_user, customer: schemas.CustomerCreate, business_id: int):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)
    check_customer_exist = (
        db.query(cm.Customer)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.email == customer.email)
        .first()
    )
    check_customer_exist_phone = (
        db.query(cm.Customer)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.phone == customer.phone)
        .first()
    )

    if check_customer_exist and check_customer_exist.is_active == False:
        for key, value in customer.model_dump(exclude_unset=True).items():
            setattr(check_customer_exist, key, value)
        check_customer_exist.is_active = True
        return check_customer_exist

    if check_customer_exist and check_customer_exist_phone and check_customer_exist.is_active == True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exist.")

    user = cm.Customer(**customer.model_dump(), business_id=business_id)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_customers(business_id, db: Session, current_user, search, skip, limit):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)
    base_query = (
        db.query(cm.Customer)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.is_active == True)
    )

    if search:
        search_query = f"%{search}%"
        base_query = (
            base_query.filter(
                or_(
                    cm.Customer.name.ilike(search_query),
                    cm.Customer.email.ilike(search_query),
                    cm.Customer.phone.ilike(search_query)
                )
            )
        )
    customers = base_query.order_by(cm.Customer.created_at.desc()).limit(limit).offset(skip).all()
    if not customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customers found"
        )
    return customers


def get_customer(business_id, customer_id, db: Session, current_user):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(cm.Customer)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.customer_id == customer_id)
        .filter(cm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    return customer


def update_customer(post: schemas.CustomerUpdate, business_id, customer_id, db: Session, current_user):
    role_permission_check(current_user)
    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(cm.Customer)
        .filter(cm.Customer.customer_id == customer_id)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Customer not found")

    base_query = (
        db.query(cm.Customer)
        .filter(cm.Customer.business_id == business_id)
    )

    if customer.email:
        email_check = base_query.filter(cm.Customer.email == customer.email)
        if email_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check email")

    if customer.phone:
        phone_check = base_query.filter(cm.Customer.phone == customer.phone).first()
        if phone_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check phone_number")
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)

    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(business_id, customer_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(cm.Customer)
        .filter(cm.Customer.customer_id == customer_id)
        .filter(cm.Customer.business_id == business_id)
        .filter(cm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer.is_active = False

    db.commit()

    return {"msg": "Customer is deleted successfully"}
