"""Tests for the debt reminder dispatcher - the code that actually sends SMS.

The API-level reminder tests live in test_debts.py. These cover the Celery
task end to end: picking up the right reminders, honouring time_of_day, and
never sending the same reminder twice.
"""

import asyncio
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select, update

from src.celery_tasks import debt_reminders
from src.config import Settings, get_settings
from src.customers import models as cm
from src.debts import models as dm
from src.main import app

from .test_debts import _client, _setup_business_with_debt

# A fixed "now" so the expectations below do not depend on when the suite runs.
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def sms_configured():
    """Pretend SMS_KEY is set, so the task does not exit as 'disabled'."""
    settings = debt_reminders.get_settings()
    with patch.object(type(settings), "sms_configured", property(lambda self: True)), \
         patch.object(type(settings), "sms_using_sandbox", property(lambda self: False)):
        yield


def add_reminder(session, debt_id, customer_id, business_id, on=TODAY, at=time(9, 0), note="please pay"):
    """Insert a reminder straight into the DB so the test controls every field."""

    async def _add():
        reminder = dm.Reminders(
            debt_id=debt_id,
            customer_id=customer_id,
            business_id=business_id,
            date=datetime.combine(on, time.min, tzinfo=timezone.utc),
            time_of_day=at,
            note=note,
            is_active=True,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder.reminder_id

    return asyncio.run(_add())


def run_dispatch(session, send_sms=None, now=NOW):
    """Run the dispatcher with the SMS call stubbed out."""
    send_sms = send_sms or AsyncMock(return_value=True)
    with patch.object(debt_reminders, "send_sms", send_sms):
        result = asyncio.run(debt_reminders.dispatch(session, now=now))
    return result, send_sms


def sent_at_of(session, reminder_id):
    async def _read():
        return (await session.execute(
            select(dm.Reminders.sent_at).where(dm.Reminders.reminder_id == reminder_id)
        )).scalar_one()

    return asyncio.run(_read())


def test_to_international():
    """Africa's Talking needs a country code; Ghanaian numbers are stored locally."""
    assert debt_reminders.to_international("0555555555") == "+233555555555"
    assert debt_reminders.to_international("0555 555 555") == "+233555555555"
    assert debt_reminders.to_international("+233555555555") == "+233555555555"
    assert debt_reminders.to_international("233555555555") == "+233555555555"
    assert debt_reminders.to_international("") is None
    assert debt_reminders.to_international(None) is None


def test_build_message():
    """A missing note must not leak into the text the customer reads."""
    due = datetime(2026, 10, 5, tzinfo=timezone.utc)

    message = debt_reminders.build_message("Debtor", Decimal("250.00"), due, None)
    assert "GHS 250.00" in message
    assert "2026-10-05" in message
    assert "None" not in message

    with_note = debt_reminders.build_message("Debtor", Decimal("250.00"), due, "Pay today")
    assert with_note.endswith("Pay today")


def test_sends_a_due_reminder(session):
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    result, send_sms = run_dispatch(session)

    assert result["due"] == 1
    assert result["sent"] == 1
    assert result["failed"] == 0
    send_sms.assert_awaited_once()
    # Stored as 0555555555, but the API must receive +233555555555.
    assert send_sms.await_args[0][0] == "+233555555555"
    assert sent_at_of(session, reminder_id) is not None

    app.dependency_overrides.clear()


def test_never_sends_the_same_reminder_twice(session):
    """sent_at is what stops a beat double-fire texting the customer again."""
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    add_reminder(session, debt_id, customer_id, business_id)

    first, first_send = run_dispatch(session)
    assert first["sent"] == 1
    first_send.assert_awaited_once()

    second, second_send = run_dispatch(session)
    assert second["due"] == 0
    assert second["sent"] == 0
    second_send.assert_not_awaited()

    app.dependency_overrides.clear()


def test_waits_for_time_of_day(session):
    """A 17:30 reminder must not go out on the 10:00 run."""
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    add_reminder(session, debt_id, customer_id, business_id, at=time(17, 30))

    result, send_sms = run_dispatch(session)

    assert result["due"] == 0
    send_sms.assert_not_awaited()

    app.dependency_overrides.clear()


def test_skips_future_inactive_and_paid(session):
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    add_reminder(session, debt_id, customer_id, business_id, on=date(2026, 10, 2))
    inactive = add_reminder(session, debt_id, customer_id, business_id)
    already_sent = add_reminder(session, debt_id, customer_id, business_id)

    async def _prepare():
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == inactive).values(is_active=False)
        )
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == already_sent).values(sent_at=NOW)
        )
        await session.execute(
            update(dm.Debt).where(dm.Debt.debt_id == debt_id).values(is_paid=True)
        )
        await session.commit()

    asyncio.run(_prepare())

    result, send_sms = run_dispatch(session)

    assert result["sent"] == 0
    send_sms.assert_not_awaited()

    app.dependency_overrides.clear()


def test_skips_customer_without_a_phone(session):
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    async def _remove_phone():
        await session.execute(
            update(cm.Customer).where(cm.Customer.customer_id == customer_id).values(phone=None)
        )
        await session.commit()

    asyncio.run(_remove_phone())
    add_reminder(session, debt_id, customer_id, business_id)

    result, send_sms = run_dispatch(session)

    assert result["skipped"] == 1
    assert result["sent"] == 0
    send_sms.assert_not_awaited()

    app.dependency_overrides.clear()


def test_failed_send_stays_unsent_for_the_next_run(session):
    """If the API rejects the text, the next hourly run must retry it."""
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    result, _ = run_dispatch(session, send_sms=AsyncMock(return_value=False))

    assert result["failed"] == 1
    assert result["sent"] == 0
    assert sent_at_of(session, reminder_id) is None

    app.dependency_overrides.clear()


def test_disabled_when_api_key_is_missing(session):
    """With no SMS_KEY the task bails out once, rather than once per customer."""
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    add_reminder(session, debt_id, customer_id, business_id)

    settings = debt_reminders.get_settings()
    with patch.object(type(settings), "sms_configured", property(lambda self: False)):
        result = asyncio.run(debt_reminders.dispatch(session, now=NOW))

    assert result["status"] == "disabled"
    assert result["sent"] == 0

    app.dependency_overrides.clear()


def sailup_settings(**overrides):
    """Real Settings with the Sailup provider switched on.

    Pydantic v2 keeps field values off the class, so these have to be set per
    instance rather than patched onto Settings itself.
    """
    base = {"SMS_PROVIDER": "sailup", "SAILUP_API_KEY": "k", "SAILUP_SENDER_ID": "BusinessBot"}
    base.update(overrides)
    return Settings(**base)


def run_sailup_send(handler, **overrides):
    """Drive send_sms against a mock transport, returning (result, requests seen)."""
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)

    settings = sailup_settings(**overrides)
    transport = httpx.MockTransport(wrapped)
    real_client = httpx.AsyncClient

    def fake_client(**kw):
        kw["transport"] = transport
        return real_client(**kw)

    with patch.object(debt_reminders, "get_settings", lambda: settings), \
         patch("httpx.AsyncClient", fake_client):
        result = asyncio.run(debt_reminders.send_sms("+233555555555", "hello"))
    return result, seen


def test_sailup_payload_matches_the_documented_shape():
    """Sailup wants from/to/body, `to` as an array, and a Bearer token."""
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = json.loads(request.content)
        return httpx.Response(202, json={"id": "abc", "status": "queued"})

    result, _ = run_sailup_send(handler, SAILUP_API_KEY="sailup_test_key")

    assert result is True
    assert captured["auth"] == "Bearer sailup_test_key"
    assert captured["json"] == {
        "from": "BusinessBot",
        "to": ["+233555555555"],
        "body": "hello",
    }
    # Sailup's resource paths need the trailing slash.
    assert captured["url"].endswith("/v1/sms/")


def test_sailup_202_means_queued_and_counts_as_sent():
    """A 202 is queued, not delivered, but the send itself succeeded."""
    result, seen = run_sailup_send(lambda request: httpx.Response(202, json={"id": "abc"}))

    assert result is True
    assert len(seen) == 1


def test_sailup_failure_returns_false_after_retries():
    result, seen = run_sailup_send(
        lambda request: httpx.Response(422, json={"detail": "unregistered sender"})
    )

    assert result is False
    assert len(seen) == debt_reminders.SEND_ATTEMPTS


def test_sailup_without_sender_id_does_not_call_the_api():
    """An unregistered `from` is rejected, so fail before spending a request."""
    def handler(request):
        pytest.fail("should not reach the API without a sender ID")

    result, seen = run_sailup_send(handler, SAILUP_SENDER_ID="")

    assert result is False
    assert seen == []


def test_africastalking_still_defaults():
    """With no SMS_PROVIDER set, Africa's Talking is the one that gets used."""
    assert get_settings().SMS_PROVIDER == "africastalking"


def test_sends_once_the_time_arrives(session):
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    add_reminder(session, debt_id, customer_id, business_id, at=time(9, 30))

    result, send_sms = run_dispatch(session)

    assert result["sent"] == 1
    send_sms.assert_awaited_once()

    app.dependency_overrides.clear()