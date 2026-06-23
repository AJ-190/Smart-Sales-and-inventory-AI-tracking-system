from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from src.users import models as um
from src.customers import models as cm
from src.debts import models as dm
from src.businesses import models as bm
from src.businesses import service


async def get_debts(business_id, db: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, db)
    
    result = await db.execute(
        select(func.sum(bm.Debt.amount).label("total_debt"))
        .where(bm.Debt.business_id == business_id)
        .where(bm.Debt.is_paid == False)
    )
    row = result.first()
    total_debt = row if row else None

    if total_debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return {"total_debt": float(total_debt)}


async def get_customers_with_deb(business_id,
                                 db: AsyncSession, 
                                 current_user, limit:int, 
                                 skip: int, search: str):
    await service.business_authorized_access(current_user, business_id, db)
    
    query = (
        select(dm.Debt,
               func(sum(dm.Debt)).label("customer_debt"))
        .join(dm.Debt, dm.Debt.customer_id == cm.Customer.customer_id)
        .where(cm.Customer.business_id == business_id)
        
    )


    if search:
        search_query = f"%{search}%"
        query = query.where(
            or_(
                cm.Customer.name.ilike(search_query),
                cm.Customer.phone.ilike(search_query),
                cm.Customer.email.ilike(search_query),
                cm.Customer.address.ilike(search_query)
            )
        )
        
    debts = (
        query.group_by(dm.Debt.customer_id)
        .order_by(dm.Debt.created_at.desc())
        .limit(limit)
        .offset(skip)
        )
    
    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No customer iwth an oustanding debt.")
    
    return debts