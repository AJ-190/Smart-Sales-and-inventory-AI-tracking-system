import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.db.database import get_async_session_maker
from src.users import models as um
from src.tasks.scheduler import scheduler
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
    async with get_async_session_maker() as session:
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




def start_report_schedulers():
    """Schedules daily, weekly, and monthly jobs in APScheduler."""
    scheduler.add_job(
        daily_report_task,
        CronTrigger(hour=19, minute=0, second=0, timezone="UTC"),
        id="daily-report-job",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_report_task,
        CronTrigger(day_of_week="sun", hour=19, minute=0, second=0, timezone="UTC"),
        id="weekly-report-job",
        replace_existing=True,
    )
    scheduler.add_job(
        monthly_report_task,
        CronTrigger(day=1, hour=19, minute=0, second=0, timezone="UTC"),
        id="monthly-report-job",
        replace_existing=True,
    )
    
    scheduler.add_job(
        process_due_reminders,
        IntervalTrigger(minutes=60),
        id="hourly-debt-reminder-job",
        replace_existing=True,
    )
    
    return scheduler
