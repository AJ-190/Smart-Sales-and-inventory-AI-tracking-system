from fastapi import APIRouter, Depends, HTTPException
from datetime import date as date_type
from src.db.database import get_db
from src.analytics import schemas, service as analytics_service
from src.products.schemas import LowStockResponse
from src.sales.schemas import DebtResponse
from src.auth import dependencies as auth_deps
from src.users import models as um


from src.auth.roles import ALL_ROLES

router = APIRouter(tags=['Reports'])

roles = ALL_ROLES

@router.get("/reports/profit/{business_id}", response_model=schemas.ProfitResponse)
async def get_profit(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date_type | None = None,
    end_date: date_type | None = None,
):
    return await analytics_service.view_profit(business_id, db=db, current_user=current_user, date=date, end_date=end_date)


@router.get("/reports/analytics/summary/{business_id}")
async def get_summary(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date_type | None = None,
    end_date: date_type | None = None
):
    return await analytics_service.get_summary(business_id, db, current_user, date, end_date)


@router.get("/reports/analytics/dashboard/{business_id}", response_model=schemas.DashboardResponse)
async def get_dashboard(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date_type | None = None,
    end_date: date_type | None = None,
):
    return await analytics_service.get_dashboard(business_id, db, current_user, date, end_date)


@router.get("/reports/analytics/low_stock", response_model=list[LowStockResponse])
async def get_low_stock(
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles]))
):
    return await analytics_service.check_stock(db, current_user)


@router.get("/reports/analytics/debts/{business_id}", response_model=list[DebtResponse])
async def get_debts(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles]))
):
    return await analytics_service.get_debts(business_id, db, current_user)

