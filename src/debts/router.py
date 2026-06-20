from fastapi import APIRouter, Depends
from src.database import get_db
from src.debts import service as debt_service
from src.auth import dependencies as auth_deps
from src.debts import schemas 

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.get("/{business_id}")
async def get_debts(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)
):
    return await debt_service.get_debts(business_id, db, current_user)

@router.get("/customers/{business_id}", response_model=list[schemas.CustomerDebt])
async def get_customers_with_debt(
    business_id: int, 
    db=Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    limit:int = 0,
    skip: int = 0,
    search: str | None = None):
    
    return await debt_service.get_customers_with_debt(business_id, db, current_user, limit, skip, search) 