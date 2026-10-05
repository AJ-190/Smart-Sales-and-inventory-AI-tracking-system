from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import dependencies as auth_deps
from src.tasks import schemas
from src.tasks.jobs import (
    JOB_METADATA,
    run_daily_report,
    run_debt_reminders,
    run_monthly_report,
    run_weekly_report,
)
from src.tasks.scheduler import scheduler
from src.users import models as um

router = APIRouter(prefix="/admin/crons", tags=["Admin Crons"])

RUNNERS = {
    "daily-report-job": run_daily_report,
    "weekly-report-job": run_weekly_report,
    "monthly-report-job": run_monthly_report,
    "hourly-debt-reminder-job": run_debt_reminders,
}


@router.get("/jobs", response_model=list[schemas.CronJobOut])
async def list_cron_jobs(
    current_user: um.Users = Depends(
        auth_deps.role_checker([um.RoleEnum.super_admin])
    ),
):
    scheduled = {job.id: job for job in scheduler.get_jobs()}

    rows = []
    for job_id, meta in JOB_METADATA.items():
        live = scheduled.get(job_id)
        rows.append(
            schemas.CronJobOut(
                id=job_id,
                name=meta["name"],
                label=meta["label"],
                description=meta["description"],
                schedule=meta["schedule"],
                trigger=meta["trigger"],
                timezone=meta["timezone"],
                running=bool(live and live.next_run_time),
                pending=bool(live and live.next_run_time is None),
                next_run=getattr(live, "next_run_time", None),
            )
        )
    return rows


@router.post("/{job_id}", response_model=schemas.CronTriggerResult)
async def trigger_cron_job(
    job_id: str,
    current_user: um.Users = Depends(
        auth_deps.role_checker([um.RoleEnum.super_admin])
    ),
):
    runner = RUNNERS.get(job_id)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scheduled job named {job_id}",
        )

    live = scheduler.get_job(job_id)
    if live is None:
        return schemas.CronTriggerResult(
            id=job_id,
            triggered=False,
            detail="The scheduler is not running, so the job was not queued.",
        )

    try:
        live.modify(next_run_time=datetime.now(live.trigger.timezone))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not queue {job_id}: {exc}",
        ) from exc

    return schemas.CronTriggerResult(
        id=job_id, triggered=True, detail=f"{job_id} queued to run now."
    )
