from fastapi import APIRouter, Depends
from src.database import get_db
from src.debts import service as debt_service
from src.auth import dependencies as auth_deps

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.get("/")
async def get_debts(
    db=Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)
):
    return await debt_service.get_debts(None, db, current_user)
