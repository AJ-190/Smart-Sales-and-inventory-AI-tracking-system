
import asyncio
import logging
from datetime import datetime, time
from decimal import Decimal
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_async_session_maker
import httpx
from sqlalchemy import select, update, func

from src.config import get_settings
from src.customers import models as cm
from src.debts import models as dm

logger = logging.getLogger(__name__)


DEFAULT_TIME_OF_DAY = time(9, 0)

GHANA_COUNTRY_CODE = "233"
SEND_ATTEMPTS = 3



async def claim_due_reminders(session:AsyncSession, limit: int = 100):

    due_ids = (
        await session.execute(
            select(dm.Reminders.reminder_id)
            .join(dm.Debt, dm.Reminders.debt_id == dm.Debt.debt_id)
            .where(
                dm.Reminders.is_active == True,
                dm.Reminders.status.in_(
                    [dm.ReminderStatus.PENDING, dm.ReminderStatus.FAILED]
                ),
                dm.Reminders.attempts < SEND_ATTEMPTS,
                dm.Reminders.date <= func.now(),
                dm.Debt.is_paid == False
            )

            .order_by(dm.Reminders.date.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )

    claimed_ids = due_ids.scalars().all()
    if not claimed_ids:
        return []


    result = (
        await session.execute(
            update(dm.Reminders)
            .where(dm.Reminders.reminder_id.in_(claimed_ids))
            .values(status=dm.ReminderStatus.SENDING, attempts= dm.Reminders.attempts +1)
            .returning(dm.Reminders)
            .execution_options(synchronize_session=False)
        )
    )

    await session.commit()
    return result.scalars().all()





def to_international(phone: str | None) -> str | None:
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


async def _send_sms_sailup(client: httpx.AsyncClient, settings, phone: str, message: str) -> bool:


    if not settings.SAILUP_SENDER_ID:
        logger.error(
            "Sailup needs SAILUP_SENDER_ID to be set in the environment to send SMS messages"
        )
        return False

    response = await client.post(
        settings.SAILUP_API_URL,
        json={
            "from": settings.SAILUP_SENDER_ID,
            "to": [phone],
            "body": message,
        },
        headers={
            "Authorization": f"Bearer {settings.SAILUP_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    if response.status_code in (200, 201, 202):
        return True

    logger.warning(
        "Sailup rejected the SMS to %s: %s %s", phone, response.status_code, response.text,
    )
    return False


async def send_sms(phone: str, message: str) -> bool:
    """Post one text to Sailup, retrying a couple of times."""
    settings = get_settings()

    if not settings.sms_configured:
        logger.error(
            "SAILUP_API_KEY or SAILUP_SENDER_ID is not set, cannot send to %s", phone,
        )
        return False

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(1, SEND_ATTEMPTS + 1):
            try:
                sent = await _send_sms_sailup(client, settings, phone, message)
            except httpx.HTTPError as error:
                logger.warning("SMS to %s failed on attempt %d: %s", phone, attempt, error)
                continue

            if sent:
                return True

    logger.error(
        "Giving up on the SMS to %s after %d attempts", phone, SEND_ATTEMPTS,
    )
    return False



logger = logging.getLogger("scheduler")

async def process_due_reminders():

    async with get_async_session_maker() as session:
        due_reminders = await claim_due_reminders(session)

        if not due_reminders:
            logger.info("No due reminders found.")
            return

        reminder_ids = [r.reminder_id for r in due_reminders]


        query = (
            select(
                dm.Reminders.reminder_id,
                dm.Reminders.business_id,
                dm.Reminders.note,
                dm.Reminders.customer_id,
                dm.Debt.amount,
                dm.Debt.due_date,
                cm.Customer.name.label("customer_name"),
                cm.Customer.phone.label("customer_phone"),
            )
            .join(dm.Debt, dm.Reminders.debt_id == dm.Debt.debt_id)
            .join(cm.Customer, dm.Reminders.customer_id == cm.Customer.customer_id)
            .where(dm.Reminders.reminder_id.in_(reminder_ids))
        )

        result = await session.execute(query)
        records = result.mappings().all()

    successful_ids = []
    failed_ids = []


    for record in records:
        logger.info(f"Processing reminder {record['reminder_id']} for business {record['business_id']}")

        phone = to_international(record["customer_phone"])
        if not phone:
            logger.error(
                "Reminder %s has no usable phone for customer %s, skipping",
                record["reminder_id"], record["customer_id"],
            )
            failed_ids.append(record["reminder_id"])
            continue

        try:

            msg = build_message(
                customer_name=record["customer_name"],
                amount=record["amount"],
                due_date=record["due_date"],
                note=record["note"],
            )

            if await send_sms(phone, msg):
                successful_ids.append(record["reminder_id"])
            else:
                logger.error(
                    "Sailup refused the reminder SMS to %s", phone
                )
                failed_ids.append(record["reminder_id"])
        except Exception as sms_err:
            logger.error(f"Failed to send SMS for reminder {record['reminder_id']}: {sms_err}")
            failed_ids.append(record["reminder_id"])

    async with get_async_session_maker() as session:
        if successful_ids:
            await session.execute(
                update(dm.Reminders)
                .where(dm.Reminders.reminder_id.in_(successful_ids))
                .values(
                    status=dm.ReminderStatus.SENT,
                    sent_at=func.now(),
                    updated_at=func.now(),
                )
            )

        if failed_ids:
            await session.execute(
                update(dm.Reminders)
                .where(dm.Reminders.reminder_id.in_(failed_ids))
                .values(status=dm.ReminderStatus.FAILED, updated_at=func.now())
            )

        await session.commit()
        logger.info(f"Processed {len(records)} reminders: {len(successful_ids)} sent, {len(failed_ids)} failed.")
