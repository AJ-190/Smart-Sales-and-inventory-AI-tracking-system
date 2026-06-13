from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from src.users import models as um
from src.businesses import models as bm


def get_debts(business_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unauthorized to perform this action")

    debts = (
        db.query(func.sum(bm.Debt.amount).label("total_debt"))
        .filter(bm.Debt.business_id == business_id)
        .filter(bm.Debt.is_paid == False)
        .first()
    )

    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return debts
