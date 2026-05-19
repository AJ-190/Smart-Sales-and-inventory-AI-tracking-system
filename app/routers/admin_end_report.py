from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app import database, models
from app import schemas 
from app.utils import dependencies
from app.jobs import sales_report
from datetime import date, datetime
from app.services.scheduler import scheduler

router = APIRouter(prefix="/admin/crons", tags=["crons"])

def permision(current_user):
    if current_user.role not in [models.RoleEnum.admin, 
                                 models.RoleEnum.super_admin, 
                                 models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    

@router.post("/daily_summery")
def run_daily(current_user: models.Users = Depends(dependencies.get_current_user)):
    permision(current_user)
    sales_report.daily_sale_summery()
    return {"status": "Daily sales cron triggered"}

@router.post("/weekly_summery")
def run_Weekly(current_user: models.Users = Depends(dependencies.get_current_user)):
    permision(current_user)
    sales_report.weekly_sale_summery()
    return {"status": "Weekly sales cron triggered"}

@router.post("/monthly_summery")
def run_monthly(current_user: models.Users = Depends(dependencies.get_current_user)):
    permision(current_user)
    sales_report.monthly_sale_summery()
    return {"status": "Monthly sales cron triggered"}

@router.get("/jobs")
def list_jobs(current_user: models.Users = Depends(dependencies.get_current_user)):
    permision(current_user)
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]