import logging

from celery import Celery
from celery.schedules import crontab
from src.config import get_settings

logger = logging.getLogger(__name__)

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
            "task": "src.celery_tasks.sales_task.daily_sale_summary",
            "schedule": crontab(hour=0, minute=0),
        },
        "weekly-sale-summary": {
            "task": "src.celery_tasks.sales_task.weekly_sale_summary",
            "schedule": crontab(hour=0, minute=0, day_of_week="mon"),
        },
        "monthly-sale-summary": {
            "task": "src.celery_tasks.sales_task.monthly_sale_summary",
            "schedule": crontab(hour=0, minute=0, day_of_month="1"),
        },
        "daily-debt-reminders": {
            "task": "src.celery_tasks.debt_reminders.dispatch_debt_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)

from src.celery_tasks import debt_reminders, sales_task  # noqa: F401 — registers tasks with the celery app


# Log the SMS wiring once at worker/beat startup. The original failure mode was
# completely silent: the schedule existed, the task existed, no key was set, and
# nothing was ever delivered. These two lines make that state obvious in logs.
_settings = get_settings()
if not _settings.sms_configured:
    logger.error(
        "SMS_KEY is not set - debt reminders are DISABLED and will send nothing. "
        "Set SMS_KEY on the worker and beat services."
    )
elif _settings.sms_using_sandbox:
    logger.warning(
        "SMS configured but pointed at SANDBOX - debt reminders will NOT reach "
        "customers. Set SMS_API_URL to the live endpoint."
    )
else:
    logger.info("SMS configured against the live endpoint.")


