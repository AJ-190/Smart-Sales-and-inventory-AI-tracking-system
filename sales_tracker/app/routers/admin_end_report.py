from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sales_tracker.app import database, models, schemas 
from sales_tracker.app.utils import dependencies
from sales_tracker.app.jobs import sales_report
from datetime import date, datetime
from sales_tracker.app.services.scheduler import scheduler

router = APIRouter(prefix="/admin/crons", tags=["crons"])

@router.post("/daily_summery")
def run_daily():
    sales_report.daily_sale_summery()
    return {"status": "Daily sales cron triggered"}

@router.post("/weekly_summery")
def run_Weekly():
    sales_report.weekly_sale_summery()
    return {"status": "Weekly sales cron triggered"}

@router.post("/monthly_summery")
def run_monthly():
    sales_report.monthly_sale_summery()
    return {"status": "Monthly sales cron triggered"}

@router.get("/jobs")
def list_jobs():
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]