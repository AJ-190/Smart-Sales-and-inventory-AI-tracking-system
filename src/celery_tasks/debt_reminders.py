"""Sends the scheduled debt reminder texts.

Celery beat runs ``dispatch_debt_reminders`` every hour. On each run we look
for reminders that are due and have not been sent yet, text the customer, and
stamp ``sent_at`` so a reminder is only ever delivered once.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from src.celery_tasks.celery_app import celery
from src.config import get_settings
from src.customers import models as cm
from src.debts import models as dm

logger = logging.getLogger(__name__)

# Used when a reminder was saved without a time of day.
DEFAULT_TIME_OF_DAY = time(9, 0)
# Africa's Talking rejects numbers without a country code, and Ghanaian numbers
# are stored locally ("0555555555"), so they are converted on the way out.
GHANA_COUNTRY_CODE = "233"
SEND_ATTEMPTS = 3


def to_international(phone: str | None) -> str | None:
    """Turn a locally stored phone number into the +233... form, or None."""
    digits = "".join(char for char in phone or "" if char.isdigit())
    if not digits:
        return None
    if digits.startswith(GHANA_COUNTRY_CODE):
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+{GHANA_COUNTRY_CODE}{digits[1:]}"
    return f"+{digits}"


def build_message(customer_name: str, amount: Decimal, due_date, note: str | None) -> str:
    """Write the text the customer receives."""
    due = due_date.date() if isinstance(due_date, datetime) else due_date
    message = (
        f"Hello {customer_name}, this is a friendly reminder about your outstanding "
        f"balance of GHS {amount:.2f}, due on {due}."
    )
    if note:
        message += f" {note}"
    return message


async def send_sms(phone: str, message: str) -> bool:
    """Post one text to Africa's Talking, retrying a couple of times."""
    settings = get_settings()
    payload = {
        "username": settings.SMS_USERNAME,
        "to": phone,
        "message": message,
    }
    if settings.SMS_SENDER_ID:
        payload["from"] = settings.SMS_SENDER_ID

    # One client for all three attempts, rather than a new socket each time.
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(1, SEND_ATTEMPTS + 1):
            try:
                response = await client.post(
                    settings.SMS_API_URL,
                    data=payload,
                    headers={
                        "apikey": settings.SMS_API_KEY,
                        "Accept": "application/json",
                    },
                )
            except httpx.HTTPError as error:
                logger.warning("SMS to %s failed on attempt %d: %s", phone, attempt, error)
                continue

            if response.status_code in (200, 201, 202):
                return True

            logger.warning(
                "SMS to %s rejected on attempt %d: %s %s",
                phone, attempt, response.status_code, response.text,
            )

    logger.error("Giving up on the SMS to %s after %d attempts", phone, SEND_ATTEMPTS)
    return False


def scheduled_at(reminder: dm.Reminders) -> datetime:
    """The exact moment a reminder is meant to go out, in UTC."""
    day = reminder.date.date() if isinstance(reminder.date, datetime) else reminder.date
    return datetime.combine(
        day,
        reminder.time_of_day or DEFAULT_TIME_OF_DAY,
        tzinfo=timezone.utc,
    )


async def due_reminders(db, now: datetime):
    """Reminders for today or earlier that are active and not sent yet."""
    # The reminder's own date is stored at midnight UTC, so "today or earlier"
    # is a plain range compare. That is index friendly and, unlike
    # func.date(column), it behaves the same on SQLite and Postgres.
    day_end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

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
            .where(dm.Reminders.sent_at.is_(None))
            .where(dm.Reminders.date < day_end)
            .where(dm.Debt.is_paid.is_(False))
            .order_by(dm.Reminders.date)
        )
    ).all()

    # The hour of day is checked here rather than in SQL: time_of_day is a wall
    # clock and the beat runs hourly, so only the reminders whose time has
    # already come are ready to go out.
    return [row for row in rows if scheduled_at(row[0]) <= now]


async def dispatch(db, now: datetime | None = None) -> dict:
    """Send every reminder that is due, then report what happened.

    ``now`` is only passed by the tests, so a run can be pinned to a fixed
    moment instead of depending on the clock.
    """
    settings = get_settings()

    # Checked once, up front. Otherwise a misconfigured deployment logs the same
    # "no API key" error once per customer and the real cause gets lost.
    if not settings.sms_configured:
        logger.error(
            "Debt reminders are DISABLED: SMS_KEY is not set, so no SMS will be sent. "
            "Set SMS_KEY (and SMS_SENDER_ID) on the worker and beat services."
        )
        return {"status": "disabled", "reason": "SMS_KEY not configured", "sent": 0}

    if settings.sms_using_sandbox:
        logger.warning(
            "SMS is pointed at the Africa's Talking SANDBOX - messages are accepted "
            "but never delivered. Set SMS_API_URL to the live endpoint for real sends."
        )

    now = now or datetime.now(timezone.utc)
    reminders = await due_reminders(db, now)

    if not reminders:
        logger.info("No debt reminders due right now")
        return {"status": "ok", "due": 0, "sent": 0, "skipped": 0, "failed": 0}

    sent = skipped = failed = 0

    for reminder, customer_name, phone, amount, due_date in reminders:
        international = to_international(phone)
        if not international:
            logger.warning("Reminder %s skipped: no usable phone number", reminder.reminder_id)
            skipped += 1
            continue

        if await send_sms(international, build_message(customer_name, amount, due_date, reminder.note)):
            # Stamping it here is what stops a second run texting them again.
            reminder.sent_at = now
            logger.info("Sent reminder %s to %s", reminder.reminder_id, international)
            sent += 1
        else:
            logger.error("Could not send reminder %s to %s", reminder.reminder_id, international)
            failed += 1

    await db.commit()

    # One line so the run is easy to find in the worker log.
    logger.info(
        "Debt reminder run complete: %d due, %d sent, %d skipped, %d failed",
        len(reminders), sent, skipped, failed,
    )
    return {
        "status": "ok",
        "due": len(reminders),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
    }


@celery.task
def dispatch_debt_reminders():
    from src.db.database import get_async_session_maker

    async def _run():
        async with get_async_session_maker() as session:
            return await dispatch(session)

    return asyncio.run(_run())
