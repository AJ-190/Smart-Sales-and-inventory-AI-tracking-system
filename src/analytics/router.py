from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from src.db.database import get_db
from src.analytics import schemas, service as analytics_service
from src.products.schemas import LowStockResponse
from src.sales.schemas import DebtResponse
from src.auth import dependencies as auth_deps
from src.users import models as um
from src.celery_tasks import sales_task as cron_tasks
from src.celery_tasks.celery_app import celery

router = APIRouter()

roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}

@router.get("/reports/profit/{business_id}", response_model=schemas.ProfitResponse)
async def get_profit(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date | None = None,
    end_date: date | None = None,
):
    return await analytics_service.view_profit(business_id, db=db, current_user=current_user, date=date, end_date=end_date)


@router.get("/reports/analytics/summery/{business_id}")
async def get_summery(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date | None = None,
    end_date: date | None = None
):
    return await analytics_service.get_summery(business_id, db, current_user, date, end_date)


@router.get("/reports/analytics/dashboard/{business_id}", response_model=schemas.DashboardResponse)
async def get_dashboard(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    date: date | None = None,
    end_date: date | None = None,
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


@router.post("/admin/crons/{job_name}")
async def run_cron_job(job_name: str, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    valid_jobs = {
        "daily_summery": "daily",
        "weekly_summery": "weekly",
        "monthly_summery": "monthly",
    }
    if job_name not in valid_jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    period = valid_jobs[job_name]
    await cron_tasks.summery(period, db=db)
    return {"status": f"{job_name} cron triggered"}


@router.get("/admin/crons/jobs")
async def list_jobs(current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    return [
        {
            "id": name,
            "name": config.get("task", ""),
            "schedule": str(config.get("schedule", "")),
        }
        for name, config in celery.conf.beat_schedule.items()
    ]
