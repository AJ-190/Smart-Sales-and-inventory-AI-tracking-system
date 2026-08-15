from fastapi import status, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.customers import models as cm
from src.customers import schemas
from src.users import models as um
from src.businesses import service
from src.businesses import models as bm
from sqlalchemy.exc import IntegrityError
from src.db.cache import CacheManager, CacheKey, build_keys


def _cache_manager() -> CacheManager:
    from src.main import app
    return CacheManager(app.state.redis)

async def create_customer(db: AsyncSession, current_user, customer: schemas.CustomerCreate, business_id: int):
    await service.business_authorized_access(current_user, business_id, db)
    
    existing = (
       await db.execute(
           select(cm.Customer)
           .where(cm.Customer.business_id == business_id)
           .where(
               (cm.Customer.email == customer.email) | (cm.Customer.phone == customer.phone)
               )
           )
       ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with that email or phone number exists")
    
    customer_add = cm.Customer(**customer.model_dump(), business_id=business_id)
    
    db.add(customer_add)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with that email or phone number already exists"
        )

    await db.refresh(customer_add)
    await _cache_manager().delete_by_pattern(
        build_keys(CacheKey.GET_CUSTOMERS, user=current_user.user_id, business_id=business_id)
    )
    return customer_add



async def get_customers(business_id: int,
                        db: AsyncSession,
                        current_user: um.Users,
                        search: str,
                        skip: int,
                        limit: int):
    
    await service.business_authorized_access(current_user, business_id, db)
    
    base_query = (
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
    )
    
    cache_key = build_keys(
        CacheKey.GET_CUSTOMERS,
        user=current_user.user_id,
        business_id=business_id,
        search=search or "",
        skip=skip,
        limit=limit,
    )
    cache_data = await _cache_manager().get(cache_key)
    if cache_data is not None:
        return cache_data
    
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
    
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customer found")
    customers = []
    
    for customer in results.scalars():
        customers.append({
            "customer_id": customer.customer_id,
            "business_id": customer.business_id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "is_active": customer.is_active,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        })
    await _cache_manager().set(cache_key, customers)

    return customers
    
    
async def get_customer(business_id: int,
                       customer_id: int,
                       db: AsyncSession,
                       current_user: um.Users
                       ):
    
        await service.business_authorized_access(current_user, business_id, db)
        
        cache_data =  await _cache_manager().get(build_keys(CacheKey.GET_CUSTOMER_BY_ID, user = current_user.user_id, business_id=business_id, customer_id=customer_id))
        if cache_data:
            return cache_data
        
        customer = (
            await(db.execute(
                select(cm.Customer)
                .where(cm.Customer.business_id == business_id)
                .where(cm.Customer.customer_id == customer_id)
                
            ))
        ).scalar_one_or_none()
        
        
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customer found.")
        
        await _cache_manager().set(build_keys(CacheKey.GET_CUSTOMER_BY_ID, user = current_user.user_id, business_id=business_id, customer_id=customer_id), {
            "customer_id": customer.customer_id,
            "business_id": customer.business_id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "is_active": customer.is_active,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        })
        
        return customer
        
        
async def update_customer(customer: schemas.CustomerUpdate,
                          business_id, 
                          customer_id, db:AsyncSession, 
                          current_user):
    
    await service.business_authorized_access(current_user, business_id, db)
    
    cache_key = build_keys(CacheKey.GET_CUSTOMER_BY_ID, user=current_user.user_id, business_id=business_id, customer_id=customer_id)
    
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
    await _cache_manager().delete_by_pattern(
        build_keys(CacheKey.GET_CUSTOMERS, user=current_user.user_id, business_id=business_id)
    )
    await _cache_manager().delete(cache_key)
    await _cache_manager().set(cache_key,customer_id_exist )
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
    await _cache_manager().delete_by_pattern(
        build_keys(CacheKey.GET_CUSTOMERS, user=current_user.user_id, business_id=business_id)
    )
    await _cache_manager().delete(
        build_keys(CacheKey.GET_CUSTOMER_BY_ID, user=current_user.user_id, business_id=business_id, customer_id=customer_id)
    )
    return customer



        
    
    
async def delete_customer(business_id, customer_id, db: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id,db)
    
    customer = await get_customer(business_id,customer_id,db, current_user)
    
    await _cache_manager().delete(build_keys(CacheKey.GET_CUSTOMER_BY_ID, user = current_user.user_id, business_id=business_id, customer_id=customer_id))
    
    await db.delete(customer)
    await db.commit()
    return