from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from src.users import models as um
from src.customers import models as cm
from src.debts import models as dm
from src.businesses import service
from src.debts import schemas




async def add_debt(post: schemas.AddDebt, business_id: int, customer_id: int, session: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)

    result = await session.execute(
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.customer_id == customer_id)
    )
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer with ID {customer_id} not found in this business")

    if not customer.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer account is deactivated")

    if post.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")

    new_debt = dm.Debt(
        business_id=business_id,
        customer_id=customer_id,
        amount=post.amount,
        due_date=post.due_date,
        is_paid=False
    )
    session.add(new_debt)
    await session.flush()

    transaction = dm.Transactions(
        debt_id=new_debt.debt_id,
        business_id=business_id,
        customer_id=customer_id,
        performer_id=current_user.user_id,
        amount_paid=0,
        note=post.note
    )
    session.add(transaction)

    await session.commit()
    await session.refresh(new_debt)
    return new_debt


async def get_debts(business_id, db: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, db)
    
    result = await db.execute(
        select(func.sum(dm.Debt.amount).label("total_debt"))
        .where(dm.Debt.business_id == business_id)
        .where(dm.Debt.is_paid == False)
    )
    row = result.first()
    total_debt = row[0] if row and row[0] else None

    if total_debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return {"total_debt": float(total_debt)}


async def get_customers_with_debt(business_id,
                                  db: AsyncSession, 
                                  current_user, limit:int, 
                                  skip: int, search: str,
                                  amount_gre: float | None = None,
                                  amount_les: float | None = None):
    await service.business_authorized_access(current_user, business_id, db)
    
    base_query = (
        select(
            dm.Debt,
            cm.Customer.name,
            cm.Customer.email,
            cm.Customer.phone,
        )
        .join(cm.Customer, dm.Debt.customer_id == cm.Customer.customer_id)
        .where(cm.Customer.business_id == business_id)
        .where(dm.Debt.is_paid == False)
    )

    if search:
        search_query = f"%{search}%"
        base_query = base_query.where(
            or_(
                cm.Customer.name.ilike(search_query),
                cm.Customer.phone.ilike(search_query),
                cm.Customer.email.ilike(search_query),
                cm.Customer.address.ilike(search_query)
            )
        )

    if amount_gre is not None:
        base_query = base_query.where(dm.Debt.amount >= amount_gre)
    if amount_les is not None:
        base_query = base_query.where(dm.Debt.amount <= amount_les)
        
    result = await db.execute(
        base_query
        .order_by(dm.Debt.created_at.desc())
        .limit(limit)
        .offset(skip)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No customer with an outstanding debt.")
    
    return [
        {
            "debt": row[0],
            "customer_name": row[1],
            "customer_email": row[2],
            "customer_phone": row[3],
        }
        for row in rows
    ]




async def get_customer_with_debt(business_id,customer_id, session: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)
    
    customer = (await session.execute(
        select(
            dm.Debt,
            cm.Customer.name,
            cm.Customer.email,
            cm.Customer.phone
        )
        .join(cm.Customer, cm.Customer.customer_id == dm.Debt.customer_id)
        .where(dm.Debt.business_id == business_id)
        .where(cm.Customer.customer_id == customer_id)
        
    )
    ).one_or_none()
    
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return {
        "debt": customer[0],
        "customer_name": customer[1],
        "customer_email": customer[2],
        "customer_phone": customer[3]
    }


async def update_customer_with_debt(post:schemas.UpdateDebt , business_id, customer_id, session:AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)
    
    debt = (
        await (
            session.execute(
                select(dm.Debt)
                .join(cm.Customer, cm.Customer.customer_id == dm.Debt.customer_id)
                .where(cm.Customer.business_id == business_id)
                .where(dm.Debt.customer_id == customer_id)
                .where(dm.Debt.is_paid == False))
        )
    ).scalar_one_or_none()
    
    if not debt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No outstanding debt found for this customer")
    
    if post.amount:
        if post.amount <= 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Amount cannot be less than or equal to zero(0)")
        
        if post.amount >= debt.amount:
            debt.amount = 0
            debt.is_paid = True
        else:
            debt.amount = debt.amount - post.amount
            
    if post.fully_paid:
        debt.amount = 0
        debt.is_paid = True
        
    if post.due_date:
        debt.due_date = post.due_date
        
    if post.amount or post.fully_paid:
        transaction = dm.Transactions(business_id=business_id, 
                                customer_id=customer_id,
                                debt_id=debt.debt_id,
                                performer_id=current_user.user_id,
                                amount_paid=post.amount if post.amount else debt.amount,
                                note=post.note if post.note else None)
        session.add(transaction)
   
    await session.commit()
    return await get_customer_with_debt(business_id, customer_id, session, current_user)
    


            
            
    
        