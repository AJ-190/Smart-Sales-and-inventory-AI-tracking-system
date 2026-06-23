from fastapi import status, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.customers import models as cm
from src.customers import schemas
from src.users import models as um
from src.businesses import service
from src.businesses import models as bm


async def create_customer(db: AsyncSession, current_user, customer: schemas.CustomerCreate, business_id: int):
    await service.business_authorized_access(current_user, business_id, db)
    
    existing_email = (
        (await
        db.execute(
            select(cm.Customer)
            .where(cm.Customer.business_id == business_id)
            .where(cm.Customer.email == customer.email)
            
        ))
    )
    
    existing_phone  = (
        (await
        db.execute(
            select(cm.Customer)
            .where(cm.Customer.business_id == business_id)
            .where(cm.Customer.email == customer.phone)
            
        ))
    )
    
    if existing_email.scalar_one_or_none() or existing_phone.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with that email or phone number exists")
    
    customer_add = cm.Customer(**customer.model_dump(), business_id=business_id)
    
    db.add(customer_add)
    await db.commit()
    await db.refresh(customer_add)
    return customer_add



async def get_customers(business_id: int,
                        db: AsyncSession,
                        current_user: str,
                        search: str,
                        skip: int,
                        limit: int):
    
    await service.business_authorized_access(current_user, business_id, db)
    
    base_query = (
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
    )
    
    if search:
        search_ = f"%{search}%"
        base_query = base_query.where(
            or_(
                cm.Customer.name.ilike(search_),
                cm.Customer.email.ilike(search_),
                cm.Customer.phone.ilike(search_)
            )
        )
    results  = await db.execute(base_query.order_by(
        cm.Customer.created_at
    ).limit(limit).offset(skip))
    
    return results.scalars().all()
    
    
async def get_customer(business_id: int,
                       customer_id: int,
                       db: AsyncSession,
                       current_user: str
                       ):
    
        await service.business_authorized_access(current_user, business_id, db)
        
        customer = (
            await(db.execute(
                select(cm.Customer)
                .where(cm.Customer.business_id == business_id)
                .where(cm.Customer.customer_id == customer_id)
                
            ))
        ).scalar_one_or_none()
        
        
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customer found.")
        
        return customer
        
        
async def update_customer(customer: schemas.CustomerUpdate,
                          business_id, 
                          customer_id, db:AsyncSession, 
                          current_user):
    
    await service.business_authorized_access(current_user, business_id, db)
    
    base_query = (
    
            select(cm.Customer)
            .where(cm.Customer.business_id == business_id)
        )
    
    

    customer_exist = (
        base_query.where(cm.Customer.customer_id == customer_id)
    )
    customer_id_exist = await db.execute(customer_exist)
    customer_id_exist = customer_id_exist.scalar_one_or_none()
    
    if not  customer_id_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not registered")
    
    check_email_or_phone_existense = (
            base_query.where(
                or_(
                    cm.Customer.phone == customer.email,
                    cm.Customer.email == customer.email,
                    
                    
                ),
                cm.Customer.customer_id != customer_id
            )
        )
    
    customer_exist_phone_or_email = await  db.execute(check_email_or_phone_existense)
    if customer_exist_phone_or_email.scalars().all():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with those credentials already exists")
    
    for key, value in customer.model_dump(exclude_unset=True).items():
        setattr(customer_id_exist, key, value)
        
    await db.commit()
    await db.refresh(customer_id_exist)
    return customer_id_exist


async def deactivate_customer( 
                              current_user: str, 
                              business_id: int, 
                              customer_id: int,
                              db: AsyncSession
                              ):
    
    await service.business_authorized_access(current_user, business_id, db)
    
    customer = (
        await(
            db.execute(
                select(cm.Customer)
                .where(cm.Customer.business_id == business_id)
                .where(cm.Customer.customer_id == customer_id)
                
            )
        )
    ).scalar_one_or_none()
    
    if customer:
        
        if customer.is_active == True:
            customer.is_active = False
            
        elif customer.is_active == False:
            customer.is_active = True
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customer found")

    await db.commit()
    await db.refresh(customer)
    return customer



        
    
    
async def delete_customer(business_id: int, 
                          customer_id: int, 
                          db: AsyncSession, 
                          current_user: str
                          ):
    await service.business_authorized_access(current_user, business_id, db)
    
    
    customer = (
        await(
            db.execute(
                select(cm.Customer)
                .where(cm.Customer.business_id == business_id)
                .where(cm.Customer.customer_id == customer_id)
                
            )
            
        )
    ).scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer does not exist")
    
    await db.delete(customer)
    await db.commit()
    return {"msg": "customer is deleted successfully."}