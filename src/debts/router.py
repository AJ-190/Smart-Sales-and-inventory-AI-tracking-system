from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.debts import service as debt_service
from src.auth import dependencies as auth_deps

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.get("/")
def get_debts(
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)
):
    return debt_service.get_debts(None, db, current_user)
