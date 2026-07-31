import asyncio
import logging
from datetime import date, datetime

import httpx
from sqlalchemy import func, select

from src.celery_tasks.celery_app import celery
from src.config import get_settings
from src.customers import models as cm
from src.debts import models as dm

logger = logging.getLogger(__name__)


def _build_message(customer_name: str, amount: float, due_date, note: str) -> str:
    due = due_date.date() if isinstance(due_date, datetime) else due_date
    return (
        f"Hello {customer_name}, this is a friendly reminder about your outstanding "
        f"balance of GHS {amount:.2f} due on {due}. {note}"
    )


async def _send_sms(phone: str, message: str) -> bool:
    settings = get_settings()
    if not settings.SMS_API_KEY:
        logger.error("SMS_API_KEY is not configured")
        return False

    payload = {
        "username": settings.SMS_USERNAME,
        "to": phone,
        "message": message,
    }
    if settings.SMS_SENDER_ID:
        payload["from"] = settings.SMS_SENDER_ID

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    settings.SMS_API_URL,
                    data=payload,
                    headers={
                        "apikey": settings.SMS_API_KEY,
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            if resp.status_code in (200, 201, 202):
                return True
            logger.warning("SMS attempt %d/3 failed for %s: %s %s", attempt + 1, phone, resp.status_code, resp.text)
        except Exception as e:
            logger.warning("SMS attempt %d/3 failed for %s: %s", attempt + 1, phone, e)

    logger.error("All 3 SMS attempts failed for %s", phone)
    return False


async def _dispatch(db) -> None:
    today = date.today()
    rows = (
        await db.execute(
            select(
                dm.Reminders,
                cm.Customer.name,
                cm.Customer.phone,
                dm.Debt.amount,
                dm.Debt.due_date,
            )
            .join(cm.Customer, cm.Customer.customer_id == dm.Reminders.customer_id)
            .join(dm.Debt, dm.Debt.debt_id == dm.Reminders.debt_id)
            .where(dm.Reminders.is_active.is_(True))
            .where(func.date(dm.Reminders.start_date) <= today)
            .where(func.date(dm.Reminders.end_date) >= today)
            .where(dm.Debt.is_paid.is_(False))
        )
    ).all()

    if not rows:
        logger.info("No debt reminders due today")
        return

    for reminder, customer_name, phone, amount, due_date in rows:
        if not phone:
            logger.warning("Reminder %s skipped: customer has no phone", reminder.reminder_id)
            continue
        message = _build_message(customer_name, amount, due_date, reminder.note)
        if await _send_sms(phone, message):
            logger.info("Debt reminder SMS sent to %s", phone)
        else:
            logger.error("Failed to send debt reminder to %s", phone)


@celery.task
def dispatch_debt_reminders():
    from src.database import get_async_session_maker

    async def _run():
        async with get_async_session_maker() as session:
            await _dispatch(session)

    asyncio.run(_run())
