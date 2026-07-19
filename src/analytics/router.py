from fastapi import APIRouter, Depends
from datetime import date
from src.database import get_db
from src.analytics import schemas, service as analytics_service
from src.products.schemas import LowStockResponse
from src.sales.schemas import DebtResponse
from src.auth import dependencies as auth_deps
from src.users import models as um
from src.celery_tasks import sales_task as cron_tasks
from src.celery_tasks.scheduler import scheduler

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


@router.post("/admin/crons/daily_summery")
async def run_daily(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    await cron_tasks.summery("daily", db=db)
    return {"status": "Daily sales cron triggered"}


@router.post("/admin/crons/weekly_summery")
async def run_weekly(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    await cron_tasks.summery("weekly", db=db)
    return {"status": "Weekly sales cron triggered"}


@router.post("/admin/crons/monthly_summery")
async def run_monthly(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    await cron_tasks.summery("monthly", db=db)
    return {"status": "Monthly sales cron triggered"}


@router.get("/admin/crons/jobs")
async def list_jobs(current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]
