
import asyncio
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select, update

from src.tasks import debt_reminders, reciept
from src.config import Settings
from src.customers import models as cm
from src.debts import models as dm
from src.main import app

from .test_debts import _client, _setup_business_with_debt


_DUE = date.today() - timedelta(days=1)
_DUE_TODAY = date.today()
_NOT_DUE = date.today() + timedelta(days=1)


# --- helpers ---------------------------------------------------------------


class _SessionCtx:
    """Stands in for ``async with get_async_session_maker() as session``.

    Yields the shared test session but does NOT close it on exit, so one
    session can back several ``process_due_reminders`` calls in one test.
    """

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


def patch_sessions(session):
    """Point the dispatcher's own session factory at the test session."""
    return patch.object(
        debt_reminders, "get_async_session_maker", lambda: _SessionCtx(session)
    )


def add_reminder(session, debt_id, customer_id, business_id, on=_DUE, note="please pay"):
    """Insert a reminder straight into the DB so the test controls every field."""

    async def _add():
        reminder = dm.Reminders(
            debt_id=debt_id,
            customer_id=customer_id,
            business_id=business_id,
            date=datetime.combine(on, time.min, tzinfo=timezone.utc),
            note=note,
            is_active=True,
            status="pending",
            attempts=0,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder.reminder_id

    return asyncio.run(_add())


def status_of(session, reminder_id):
    async def _read():
        return (
            await session.execute(
                select(dm.Reminders.status, dm.Reminders.attempts).where(
                    dm.Reminders.reminder_id == reminder_id
                )
            )
        ).one()

    return asyncio.run(_read())


def sent_at_of(session, reminder_id):
    async def _read():
        return (
            await session.execute(
                select(dm.Reminders.sent_at).where(dm.Reminders.reminder_id == reminder_id)
            )
        ).scalar_one()

    return asyncio.run(_read())


def run_process(send_sms, session):
    """Run the dispatcher with the SMS call stubbed out."""
    with patch_sessions(session), patch.object(debt_reminders, "send_sms", send_sms):
        asyncio.run(debt_reminders.process_due_reminders())


def sailup_settings(**overrides):
    """Real Settings with working Sailup credentials.

    Pydantic v2 keeps field values off the class, so these have to be set per
    instance rather than patched onto Settings itself.
    """
    base = {"SAILUP_API_KEY": "k", "SAILUP_SENDER_ID": "BusinessBot"}
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


# --- text helpers ----------------------------------------------------------


def test_to_international():
    """Sailup needs a country code; Ghanaian numbers are stored locally."""
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


# --- Sailup transport ------------------------------------------------------


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

    def handler(request):
        pytest.fail("should not reach the API without a sender ID")

    result, seen = run_sailup_send(handler, SAILUP_SENDER_ID="")

    assert result is False
    assert seen == []


def test_send_sms_is_skipped_when_credentials_are_blank():
    result, seen = run_sailup_send(
        lambda request: pytest.fail("should not reach the API without an API key"),
        SAILUP_API_KEY="",
    )

    assert result is False
    assert seen == []


def test_sms_configured_requires_both_key_and_sender_id():
    assert sailup_settings().sms_configured is True
    assert sailup_settings(SAILUP_API_KEY="").sms_configured is False
    assert sailup_settings(SAILUP_SENDER_ID="").sms_configured is False
    assert sailup_settings(SAILUP_API_KEY="  ").sms_configured is False




def setup_debt(session):
    """A business with one customer and one unpaid debt."""
    client = _client(session)
    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)
    return business_id, customer_id, debt_id


def claim(session, **kwargs):
    return asyncio.run(debt_reminders.claim_due_reminders(session, **kwargs))


def test_claims_a_due_reminder_and_marks_it_sending(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    claimed = claim(session)

    assert [r.reminder_id for r in claimed] == [reminder_id]
    status, attempts = status_of(session, reminder_id)
    assert status == "sending"
    assert attempts == 1


def test_claiming_twice_does_not_double_count(session):
    """status flips to 'sending', so a second scheduler tick must find nothing."""
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id)

    assert len(claim(session)) == 1
    assert claim(session) == []


def test_increments_attempts_per_claim(session):
    """attempts is the retry counter, so it must climb on every claim."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    claim(session)
    assert status_of(session, reminder_id)[1] == 1

    # Put it back to pending to simulate a retry after a failure.
    async def _requeue():
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == reminder_id).values(status="pending")
        )
        await session.commit()

    asyncio.run(_requeue())
    claim(session)
    assert status_of(session, reminder_id)[1] == 2


def test_ignores_future_reminders(session):
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id, on=_NOT_DUE)

    assert claim(session) == []


def test_ignores_inactive_reminders(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _deactivate():
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == reminder_id).values(is_active=False)
        )
        await session.commit()

    asyncio.run(_deactivate())
    assert claim(session) == []


def test_ignores_reminders_for_paid_debts(session):
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id)

    async def _settle():
        await session.execute(
            update(dm.Debt).where(dm.Debt.debt_id == debt_id).values(is_paid=True)
        )
        await session.commit()

    asyncio.run(_settle())
    assert claim(session) == []


def test_ignores_reminders_that_were_already_sent(session):
    """A delivered reminder is terminal and must never fire again."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _mark():
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == reminder_id).values(status="sent")
        )
        await session.commit()

    asyncio.run(_mark())
    assert claim(session) == []


def test_retries_a_failed_reminder(session):
    """A failed send stays unstamped, so the next tick must try it again."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _mark():
        await session.execute(
            update(dm.Reminders).where(dm.Reminders.reminder_id == reminder_id).values(status="failed")
        )
        await session.commit()

    asyncio.run(_mark())
    assert [r.reminder_id for r in claim(session)] == [reminder_id]


def test_stops_retrying_once_attempts_are_exhausted(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _mark():
        await session.execute(
            update(dm.Reminders)
            .where(dm.Reminders.reminder_id == reminder_id)
            .values(status="failed", attempts=debt_reminders.SEND_ATTEMPTS)
        )
        await session.commit()

    asyncio.run(_mark())
    assert claim(session) == []


def test_a_failed_reminder_is_claimed_and_reset_to_sending(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _mark():
        await session.execute(
            update(dm.Reminders)
            .where(dm.Reminders.reminder_id == reminder_id)
            .values(status="failed", attempts=1)
        )
        await session.commit()

    asyncio.run(_mark())
    assert [r.reminder_id for r in claim(session)] == [reminder_id]
    status, attempts = status_of(session, reminder_id)
    assert (status, attempts) == ("sending", 2)


def test_respects_the_limit(session):
    business_id, customer_id, debt_id = setup_debt(session)
    for day in (_DUE, _DUE_TODAY, _DUE_TODAY):
        add_reminder(session, debt_id, customer_id, business_id, on=day)

    assert len(claim(session, limit=2)) == 2


def test_claim_is_empty_when_nothing_is_due(session):
    setup_debt(session)
    assert claim(session) == []




def test_marks_a_delivered_reminder_as_sent(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    send_sms = AsyncMock(return_value=True)
    run_process(send_sms, session)

    send_sms.assert_awaited_once()
    assert status_of(session, reminder_id)[0] == "sent"
    assert sent_at_of(session, reminder_id) is not None

    app.dependency_overrides.clear()


def test_sends_the_amount_and_due_date_the_customer_owes(session):
    """The text is the whole point of the reminder, so pin its content."""
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id)

    send_sms = AsyncMock(return_value=True)
    run_process(send_sms, session)

    phone, message = send_sms.await_args[0]
    assert phone == "+233555555555"
    assert "GHS 250.00" in message
    assert "Debtor" in message
    assert "please pay" in message

    app.dependency_overrides.clear()


def test_a_raised_send_is_marked_failed_and_left_retryable(session):
    """If the send blows up, the next scheduler tick must try that one again."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    run_process(AsyncMock(side_effect=RuntimeError("boom")), session)

    assert status_of(session, reminder_id)[0] == "failed"
    assert sent_at_of(session, reminder_id) is None

    app.dependency_overrides.clear()


def test_a_rejected_send_is_not_recorded_as_sent(session):
    """send_sms returns False when Sailup refuses; that must count as a failure."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    run_process(AsyncMock(return_value=False), session)

    assert status_of(session, reminder_id)[0] == "failed"
    assert sent_at_of(session, reminder_id) is None

    app.dependency_overrides.clear()


def test_customer_without_a_phone_is_not_sent_to(session):
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder(session, debt_id, customer_id, business_id)

    async def _remove_phone():
        await session.execute(
            update(cm.Customer).where(cm.Customer.customer_id == customer_id).values(phone=None)
        )
        await session.commit()

    asyncio.run(_remove_phone())

    send_sms = AsyncMock(return_value=True)
    run_process(send_sms, session)


    send_sms.assert_not_awaited()
    assert status_of(session, reminder_id)[0] == "failed"
    assert sent_at_of(session, reminder_id) is None

    app.dependency_overrides.clear()


def test_customer_with_a_local_phone_is_normalised_before_sending(session):
    """0555555555 is stored locally but Sailup needs +233555555555."""
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id)

    send_sms = AsyncMock(return_value=True)
    run_process(send_sms, session)

    assert send_sms.await_args[0][0] == "+233555555555"

    app.dependency_overrides.clear()


def test_nothing_due_sends_nothing(session):
    business_id, customer_id, debt_id = setup_debt(session)
    add_reminder(session, debt_id, customer_id, business_id, on=_NOT_DUE)

    send_sms = AsyncMock(return_value=True)
    run_process(send_sms, session)

    send_sms.assert_not_awaited()

    app.dependency_overrides.clear()




class _FakeMember:
    def __init__(self, business_id=29):
        self.business_id = business_id


def make_report(**kwargs):
    now = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
    defaults = dict(
        phone="+233555555555",
        current_user=_FakeMember(),
        session=object(),
        start_date=now - timedelta(days=7),
        end_date=now,
        title="Daily Sales Summary",
    )
    defaults.update(kwargs)
    return reciept.RecieptReportGenerator(**defaults)


def test_report_message_has_the_business_report_sections():
    """Section order mirrors the old emailed report."""
    summary = {
        "total_sales": 3,
        "total_revenue": 1200.5,
        "total_profit": 300.25,
        "sold_quantity": 7,
        "cash_total": 1,
        "momo_total": 2,
        "card_total": 0,
        "best_selling_product": "WIFI",
    }

    with patch.object(reciept, "get_summary", AsyncMock(return_value=summary)):
        message = asyncio.run(make_report().build_analytics_message())

    assert message.startswith("AUTOMATED REPORT")
    assert "Total Revenue: GHS 1,200.50" in message
    assert "Total Profit: GHS 300.25" in message
    assert "Total Orders: 3" in message
    assert "Units Sold: 7" in message
    assert "Payment breakdown" in message
    assert "Cash: 1" in message
    assert "Mobile money: 2" in message
    assert "Card: 0" in message
    assert "Best selling product: WIFI" in message

    # Sections must appear in the order a reader expects.
    order = [
        message.index("Total Revenue"),
        message.index("Payment breakdown"),
        message.index("Best selling product"),
    ]
    assert order == sorted(order)


def test_report_message_uses_the_schedule_title():
    for title in ("Daily Sales Summary", "Weekly Performance Overview", "Monthly Revenue Report"):
        with patch.object(reciept, "get_summary", AsyncMock(return_value={})):
            message = asyncio.run(make_report(title=title).build_analytics_message())
        assert title in message


def test_report_message_stays_within_sms_limits():
    """A long product name must not push the body past a sane segment count."""
    summary = {
        "total_sales": 999999,
        "total_revenue": 9876543.21,
        "total_profit": 1234567.89,
        "sold_quantity": 999999,
        "cash_total": 111111,
        "momo_total": 222222,
        "card_total": 333333,
        "best_selling_product": "Premium Wireless Noise Cancelling Over-Ear Headphones",
    }

    with patch.object(reciept, "get_summary", AsyncMock(return_value=summary)):
        message = asyncio.run(make_report().build_analytics_message())

    # 160 chars per GSM segment; 4 is the point where gateways start truncating.
    assert len(message) <= 640


def test_report_message_handles_an_empty_business():
    """No sales must render a clear notice, not zeros or 'None'."""
    with patch.object(reciept, "get_summary", AsyncMock(return_value={})):
        message = asyncio.run(make_report().build_analytics_message())

    assert "No sales data available" in message
    assert "Daily Sales Summary" in message
    assert "None" not in message
    # A zero-sales period has no meaningful figures to report.
    assert "Total Revenue" not in message
    assert "Best selling product" not in message


def test_report_message_passes_plain_dates(session):
    """get_summary filters on func.date(), so a datetime bound is a bug."""
    seen = {}

    async def _capture(business_id, db, current_user, date, end_date):
        seen["start"] = date
        seen["end"] = end_date
        return {}

    gen = make_report()
    with patch.object(reciept, "get_summary", _capture):
        asyncio.run(gen.build_analytics_message())

    assert isinstance(seen["start"], date) and not isinstance(seen["start"], datetime)
    assert isinstance(seen["end"], date) and not isinstance(seen["end"], datetime)


def test_report_sms_is_skipped_when_sailup_is_unconfigured(session):
    gen = make_report()
    settings = sailup_settings(SAILUP_API_KEY="")

    with patch.object(reciept, "get_settings", lambda: settings), \
         patch.object(reciept, "send_sms", AsyncMock()) as send_sms:
        assert asyncio.run(gen.send_report_smss()) is False

    send_sms.assert_not_awaited()


def test_report_sms_sends_the_built_message(session):
    gen = make_report()
    settings = sailup_settings()
    summary = {
        "total_sales": 4,
        "total_revenue": 500.0,
        "total_profit": 100.0,
        "profit_margin": 20.0,
        "sold_quantity": 7,
        "cash_total": 3,
        "momo_total": 1,
        "card_total": 0,
        "best_selling_product": "Desk",
    }

    with patch.object(reciept, "get_settings", lambda: settings), \
         patch.object(reciept, "get_summary", AsyncMock(return_value=summary)), \
         patch.object(reciept, "send_sms", AsyncMock(return_value=True)) as send_sms:
        assert asyncio.run(gen.send_report_smss()) is True

    send_sms.assert_awaited_once()
    assert send_sms.await_args[0][0] == "+233555555555"
    assert "GHS 500.00" in send_sms.await_args[0][1]


def test_report_sms_reports_a_rejected_send_as_false(session):
    gen = make_report()
    settings = sailup_settings()

    summary = {"total_sales": 2, "total_revenue": 50.0, "total_profit": 10.0}

    with patch.object(reciept, "get_settings", lambda: settings), \
         patch.object(reciept, "get_summary", AsyncMock(return_value=summary)), \
         patch.object(reciept, "send_sms", AsyncMock(return_value=False)):
        assert asyncio.run(gen.send_report_smss()) is False


def test_report_sms_swallows_an_analytics_failure(session):
    """A bad report must not take the scheduler down with it."""
    gen = make_report()
    settings = sailup_settings()

    with patch.object(reciept, "get_settings", lambda: settings), \
         patch.object(reciept, "get_summary", AsyncMock(side_effect=RuntimeError("db down"))), \
         patch.object(reciept, "send_sms", AsyncMock()) as send_sms:
        assert asyncio.run(gen.send_report_smss()) is False

    send_sms.assert_not_awaited()


# --- frontend/server date alignment ----------------------------------------


@pytest.fixture
def ahead_of_utc_tz():
    """Puts the process clock in a timezone whose date is ahead of UTC."""
    import os
    import time as _time
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Pacific/Kiritimati"
    _time.tzset()
    yield
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    _time.tzset()


def test_today_in_utc_is_accepted_even_when_local_date_is_ahead(client, session, ahead_of_utc_tz):
    """The frontend sends the UTC day, so local-date skew must not reject it."""
    from src.debts import models as dm_models
    from src.debts import schemas as dm_schemas
    from src.debts import service as debt_service

    _setup_business_with_debt(client, session)
    client.headers.pop("Authorization", None)

    utc_today = datetime.now(timezone.utc).date()
    if date.today() == utc_today:
        pytest.skip("host timezone is not ahead of UTC")

    from src.users import models as um_models

    async def _seed():
        debt = (await session.execute(select(dm_models.Debt))).scalars().first()
        reminder = dm_models.Reminders(
            debt_id=debt.debt_id,
            business_id=debt.business_id,
            customer_id=debt.customer_id,
            date=datetime.combine(utc_today, time.min, tzinfo=timezone.utc),
            note="",
        )
        session.add(reminder)
        await session.commit()
        admin = (await session.execute(select(um_models.Users))).scalars().first()
        return debt, admin

    debt, admin = asyncio.run(_seed())

    payload = dm_schemas.ScheduleReminder(
        debt_id=debt.debt_id,
        customer_id=debt.customer_id,
        date=utc_today,
        time_of_day=time(9, 0),
        note="",
    )

    async def _call():
        return await debt_service.set_reminders(
            debt.business_id, admin, session, payload
        )

    reminder = asyncio.run(_call())
    assert reminder.date.date() == utc_today


# --- time_of_day is honoured -----------------------------------------------


def add_reminder_at(session, debt_id, customer_id, business_id, on, time_of_day, note="please pay"):
    async def _add():
        reminder = dm.Reminders(
            debt_id=debt_id,
            customer_id=customer_id,
            business_id=business_id,
            date=datetime.combine(on, time.min, tzinfo=timezone.utc),
            time_of_day=time_of_day,
            note=note,
            is_active=True,
            status="pending",
            attempts=0,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder.reminder_id

    return asyncio.run(_add())


def test_reminder_due_later_today_is_not_claimed_yet(session):
    """time_of_day is chosen in the UI, so it must gate the send."""
    now = datetime.now(timezone.utc)
    if now.time() >= time(23, 59):
        pytest.skip("no time left in the UTC day")
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder_at(session, debt_id, customer_id, business_id, _DUE_TODAY, time(23, 59))

    assert claim(session) == []
    assert status_of(session, reminder_id) == ("pending", 0)


def test_reminder_whose_time_has_passed_is_claimed(session):
    now = datetime.now(timezone.utc)
    if now.time() <= time(0, 2):
        pytest.skip("start of the UTC day")
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder_at(session, debt_id, customer_id, business_id, _DUE_TODAY, time(0, 1))

    assert [r.reminder_id for r in claim(session)] == [reminder_id]
    assert status_of(session, reminder_id) == ("sending", 1)


def test_yesterday_with_a_future_time_is_still_due(session):
    """Only today is gated by time_of_day; a past day always sends."""
    business_id, customer_id, debt_id = setup_debt(session)
    reminder_id = add_reminder_at(session, debt_id, customer_id, business_id, _DUE, time(23, 59))

    assert [r.reminder_id for r in claim(session)] == [reminder_id]
    assert status_of(session, reminder_id) == ("sending", 1)


def test_missing_time_of_day_defaults_to_nine_in_the_morning(session):
    business_id, customer_id, debt_id = setup_debt(session)

    async def _add_null():
        reminder = dm.Reminders(
            debt_id=debt_id,
            customer_id=customer_id,
            business_id=business_id,
            date=datetime.combine(_DUE_TODAY, time.min, tzinfo=timezone.utc),
            time_of_day=None,
            note="please pay",
            is_active=True,
            status="pending",
            attempts=0,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder.reminder_id

    reminder_id = asyncio.run(_add_null())

    assert debt_reminders.DEFAULT_TIME_OF_DAY == time(9, 0)
    now = datetime.now(timezone.utc)
    expected_due = now.time() >= debt_reminders.DEFAULT_TIME_OF_DAY
    claimed = [r.reminder_id for r in claim(session)]
    assert claimed == ([reminder_id] if expected_due else [])
