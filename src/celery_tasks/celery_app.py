from celery import Celery
from celery.schedules import crontab
from src.config import get_settings

celery = Celery(
    "worker",
    broker=get_settings().REDIS_URL,
    backend=get_settings().REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-sale-summary": {
            "task": "src.celery_tasks.sales_task.daily_sale_summery",
            "schedule": crontab(hour=0, minute=0),
        },
        "weekly-sale-summary": {
            "task": "src.celery_tasks.sales_task.weekly_sale_summery",
            "schedule": crontab(hour=0, minute=0, day_of_week="mon"),
        },
        "monthly-sale-summary": {
            "task": "src.celery_tasks.sales_task.monthly_sale_summery",
            "schedule": crontab(hour=0, minute=0, day_of_month="1"),
        },
        "daily-debt-reminders": {
            "task": "src.celery_tasks.debt_reminders.dispatch_debt_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)

from src.celery_tasks import debt_reminders, sales_task  # noqa: F401 — registers tasks with the celery app


