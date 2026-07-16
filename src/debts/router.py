from fastapi import APIRouter, Depends
from src.database import get_db
from src.debts import service as debt_service
from src.auth import dependencies as auth_deps
from src.debts import schemas
from src.users import models as um
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.get("/{business_id}")
async def get_debts(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))
):
    return await debt_service.get_debts(business_id, db, current_user)

@router.get("/customers/{business_id}", response_model=list[schemas.CustomerDebt])
async def get_customers_with_debt(
    business_id: int, 
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager])),
    limit:int = 0,
    skip: int = 0,
    amount_gre: float | None = None,
    amount_les: float | None =  None,
    search: str | None = None):
    
    return await debt_service.get_customers_with_debt(business_id, db, current_user, limit, skip, search, amount_gre, amount_les) 


@router.get("/repay_debt")
async def repay_debt(business_id, 
                     customer_id,
                     debt_id,
                     current_user,
                     paid: bool | None = None,
                     amount: float | None =  None,
                     db:AsyncSession = Depends(get_db)):
    return await debt_service.repay_debt(business_id, customer_id, debt_id, db, current_user, paid, amount)