from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from src.users import models as um
from src.businesses import models as bm


async def get_debts(business_id, db: AsyncSession, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unauthorized to perform this action")

    result = await db.execute(
        select(func.sum(bm.Debt.amount).label("total_debt"))
        .where(bm.Debt.business_id == business_id)
        .where(bm.Debt.is_paid == False)
    )
    debts = result.first()

    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return debts
