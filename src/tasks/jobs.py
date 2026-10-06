import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.db.database import job_engine, job_session_maker
from src.users import models as um
from apscheduler.schedulers.base import STATE_STOPPED
from src.tasks.scheduler import scheduler, MISFIRE_GRACE_TIME
from src.tasks.reciept import RecieptReportGenerator
from src.tasks.debt_reminders import process_due_reminders, to_international
from src.middleware.logging import logger

logger = logger("scheduler")




def daily_report_dates():
    target_date = datetime.now(timezone.utc).date()
    start_date = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end_date = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)
    return start_date, end_date


def weekly_report_dates():
    target_date = datetime.now(timezone.utc).date()
    start_date = datetime.combine(target_date - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc)
    end_date = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)
    return start_date, end_date


def monthly_report_dates():
    target_date = datetime.now(timezone.utc).date()

    first_day_of_month = target_date.replace(day=1)

    last_day_prev_month = first_day_of_month - timedelta(days=1)
    start_date = datetime.combine(last_day_prev_month.replace(day=1), datetime.min.time(), tzinfo=timezone.utc)
    end_date = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)
    return start_date, end_date




async def get_business_members(session):
    """Fetches verified, active admin and manager members."""
    query = (
        select(um.Users, um.BusinessMember)
        .join(um.BusinessMember, um.Users.user_id == um.BusinessMember.user_id)
        .where(um.ACTIVE_MEMBERSHIP)
        .where(um.BusinessMember.role.in_(["admin", "manager"]))
        .where(um.Users.is_verified == True)
        .where(um.Users.is_active == True)
    )
    result = await session.execute(query)
    return result.all()


async def process_report_data(start_date, end_date, title: str = "Sales Summary"):
    """Generates and dispatches receipt reports for all target admin/manager users."""
    async with job_session_maker() as session:
        members = await get_business_members(session)

        if not members:
            logger.info("No eligible business members found for report generation.")
            return

        for user, member in members:
            raw_phone = getattr(user, "phone", None)
            formatted_phone = to_international(raw_phone) if isinstance(raw_phone, str) else None

            if not formatted_phone:
                logger.error(f"Invalid or missing phone number for user ID {user.user_id}: {raw_phone}")
                continue

            try:
                report_generator = RecieptReportGenerator(
                    phone=formatted_phone,
                    current_user=member,
                    session=session,
                    start_date=start_date,
                    end_date=end_date,
                    title=title,
                )

                sent = await report_generator.send_report_smss()

                if not sent:
                    logger.error(f"Failed to send report SMS to {formatted_phone}")
                else:
                    logger.info(f"Report SMS successfully sent to {formatted_phone}")

            except Exception as e:
                logger.error(f"Error executing report generation for user ID {user.user_id}: {e}")




async def daily_report_task():
    start_date, end_date = daily_report_dates()
    await process_report_data(start_date, end_date, "Daily Sales Summary")


async def weekly_report_task():
    start_date, end_date = weekly_report_dates()
    await process_report_data(start_date, end_date, "Weekly Performance Overview")


async def monthly_report_task():
    start_date, end_date = monthly_report_dates()
    await process_report_data(start_date, end_date, "Monthly Revenue Report")





def _run_job(coro):

    async def _drive():
        try:
            return await coro
        finally:
            await job_engine.dispose()

    return asyncio.run(_drive())


def run_daily_report():
    _run_job(daily_report_task())


def run_weekly_report():
    _run_job(weekly_report_task())


def run_monthly_report():
    _run_job(monthly_report_task())


def run_debt_reminders():
    _run_job(process_due_reminders())


JOB_METADATA = {
    "daily-report-job": {
        "name": "daily_summary",
        "label": "Daily Summary",
        "description": "Daily sales and revenue summary, texted to every admin and manager.",
        "schedule": "Every day at 19:00",
        "trigger": "cron",
        "timezone": "UTC",
    },
    "weekly-report-job": {
        "name": "weekly_summary",
        "label": "Weekly Summary",
        "description": "Seven-day performance overview for the week just ended.",
        "schedule": "Every Sunday at 19:00",
        "trigger": "cron",
        "timezone": "UTC",
    },
    "monthly-report-job": {
        "name": "monthly_summary",
        "label": "Monthly Summary",
        "description": "Month-to-date revenue report, covering the 1st onwards.",
        "schedule": "1st of each month at 19:00",
        "trigger": "cron",
        "timezone": "UTC",
    },
    "hourly-debt-reminder-job": {
        "name": "debt_reminders",
        "label": "Debt Reminders",
        "description": "Sends any reminder SMS that has reached its scheduled day.",
        "schedule": "Every 60 minutes",
        "trigger": "interval",
        "timezone": "Africa/Accra",
    },
}


# Same window APScheduler itself allows a late run to fire in, so an overdue
# job carried across a restart is honoured only while that grace still holds.
GRACE_PERIOD = MISFIRE_GRACE_TIME


JOB_SPECS = [
    (
        "daily-report-job",
        run_daily_report,
        CronTrigger(hour=19, minute=0, second=0, timezone="UTC"),
    ),
    (
        "weekly-report-job",
        run_weekly_report,
        CronTrigger(day_of_week="sun", hour=19, minute=0, second=0, timezone="UTC"),
    ),
    (
        "monthly-report-job",
        run_monthly_report,
        CronTrigger(day=1, hour=19, minute=0, second=0, timezone="UTC"),
    ),
    (
        "hourly-debt-reminder-job",
        run_debt_reminders,
        IntervalTrigger(minutes=60),
    ),
]


def _stored_next_run(job_id):
    """Next run time recorded for ``job_id``, read before registration overwrites it.

    While the scheduler is stopped, ``get_job`` only searches jobs this process
    has added so far and ignores the persisted job store. Lifespan registers jobs
    *before* calling ``start()``, so on a cold boot it would otherwise see
    nothing and a run that came due while the app was down would be lost without
    ever being noticed.
    """
    try:
        if scheduler.state == STATE_STOPPED:
            for job, _store, _replace in scheduler._pending_jobs:
                if job.id == job_id:
                    return getattr(job, "next_run_time", None)

            jobstores = scheduler._jobstores
            store = jobstores["default"] if isinstance(jobstores, dict) else None
            if store is None:
                return None
            job = store.lookup_job(job_id)
        else:
            job = scheduler.get_job(job_id)
    except Exception:  # noqa: BLE001 - a broken job store must not stop boot
        return None

    return getattr(job, "next_run_time", None) if job is not None else None


def start_report_schedulers():
    """Register the report and reminder jobs, keeping the schedule already owed.

    ``replace_existing`` recomputes ``next_run_time`` from the current moment, so
    two things were lost on every restart. A run that came due while the app was
    down was dropped and re-queued for the next occurrence -- a restart at 19:05
    discarded the 19:00 report even though ``misfire_grace_time`` was three hours.
    And a future time was pushed back to now plus the full period, so the hourly
    debt reminders drifted an hour on each restart and never fired at all if the
    app cycled more often than that.

    Read the stored time first and hand it back to ``add_job``. Only a run older
    than the grace window is given up on: that one would fail anyway, so the
    trigger's next occurrence takes over.
    """
    now = datetime.now(timezone.utc)

    for job_id, func, trigger in JOB_SPECS:
        stored = _stored_next_run(job_id)
        owed = None

        if stored is not None:
            if stored.tzinfo is None:
                stored = stored.replace(tzinfo=timezone.utc)
            if (now - stored).total_seconds() <= GRACE_PERIOD:
                owed = stored

        kwargs = {"next_run_time": owed} if owed is not None else {}

        scheduler.add_job(
            func,
            trigger,
            id=job_id,
            replace_existing=True,
            **kwargs,
        )

    return scheduler
