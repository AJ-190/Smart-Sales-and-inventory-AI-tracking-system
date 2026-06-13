from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.celery_tasks.tasks import (
    daily_sale_summery,
    weekly_sale_summery,
    monthly_sale_summery,
)
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler():
    scheduler.add_job(
        daily_sale_summery,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_sale_summery",
        name="Daily Sale Summary",
        replace_existing=True,
        misfire_grace_time=None,
    )

    scheduler.add_job(
        weekly_sale_summery,
        trigger=CronTrigger(day_of_week="mon", hour=0, minute=0),
        id="weekly_sale_summery",
        name="Weekly Sale Summary",
        replace_existing=True,
        misfire_grace_time=None,
    )

    scheduler.add_job(
        monthly_sale_summery,
        trigger=CronTrigger(day=1, hour=0, minute=0),
        id="monthly_sale_summery",
        name="Monthly Sale Summary",
        replace_existing=True,
        misfire_grace_time=None,
    )

    scheduler.start()
    logger.info("[SCHEDULER] All cron jobs registered and running.")
