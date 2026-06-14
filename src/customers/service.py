from fastapi import status, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.customers import models as cm
from src.customers import schemas
from src.users import models as um


async def role_permission_check(current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager,
        um.RoleEnum.cashier
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unauthorized to perform this action")


async def check_current_user_business(db: AsyncSession, current_user, business_id: int):
    result = await db.execute(
        select(um.BusinessMember)
        .where(um.BusinessMember.user_id == current_user.user_id)
        .where(um.BusinessMember.business_id == business_id)
    )
    business = result.first()

    if not business:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")


async def create_customer(db: AsyncSession, current_user, customer: schemas.CustomerCreate, business_id: int):
    await role_permission_check(current_user)

    await check_current_user_business(db, current_user, business_id)

    email_result = await db.execute(
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.email == customer.email)
    )
    check_customer_exist = email_result.scalar_one_or_none()

    phone_result = await db.execute(
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.phone == customer.phone)
    )
    check_customer_exist_phone = phone_result.scalar_one_or_none()

    if check_customer_exist and check_customer_exist.is_active == False:
        for key, value in customer.model_dump(exclude_unset=True).items():
            setattr(check_customer_exist, key, value)
        check_customer_exist.is_active = True
        return check_customer_exist

    if check_customer_exist and check_customer_exist_phone and check_customer_exist.is_active == True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exist.")

    user = cm.Customer(**customer.model_dump(), business_id=business_id)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_customers(business_id, db: AsyncSession, current_user, search, skip, limit):
    await role_permission_check(current_user)

    await check_current_user_business(db, current_user, business_id)
    query = (
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.is_active == True)
    )

    if search:
        search_query = f"%{search}%"
        query = query.where(
            or_(
                cm.Customer.name.ilike(search_query),
                cm.Customer.email.ilike(search_query),
                cm.Customer.phone.ilike(search_query)
            )
        )
    query = query.order_by(cm.Customer.created_at.desc()).limit(limit).offset(skip)
    result = await db.execute(query)
    customers = result.scalars().all()

    if not customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customers found"
        )
    return customers


async def get_customer(business_id, customer_id, db: AsyncSession, current_user):
    await role_permission_check(current_user)

    await check_current_user_business(db, current_user, business_id)

    result = await db.execute(
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.customer_id == customer_id)
        .where(cm.Customer.is_active == True)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    return customer


async def update_customer(post: schemas.CustomerUpdate, business_id, customer_id, db: AsyncSession, current_user):
    await role_permission_check(current_user)
    await check_current_user_business(db, current_user, business_id)

    result = await db.execute(
        select(cm.Customer)
        .where(cm.Customer.customer_id == customer_id)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.is_active == True)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Customer not found")

    if customer.email:
        email_check_result = await db.execute(
            select(cm.Customer).where(cm.Customer.email == customer.email)
        )
        email_check = email_check_result.first()
        if email_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check email")

    if customer.phone:
        phone_check_result = await db.execute(
            select(cm.Customer).where(cm.Customer.phone == customer.phone)
        )
        phone_check = phone_check_result.first()
        if phone_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check phone_number")

    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)
    return customer


async def delete_customer(business_id, customer_id, db: AsyncSession, current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    await check_current_user_business(db, current_user, business_id)

    result = await db.execute(
        select(cm.Customer)
        .where(cm.Customer.customer_id == customer_id)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.is_active == True)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer.is_active = False

    await db.commit()

    return {"msg": "Customer is deleted successfully"}
