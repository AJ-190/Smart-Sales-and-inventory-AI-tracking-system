import asyncio
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, update
from src.businesses import models as bm
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.db.database import get_db
from src.main import app
from src.debts import models as dm


def _setup_business_with_debt(client, session):
    res = client.post("/users/sign_up", json={
        "name": "RemAdmin", "email": "rem_admin@test.com",
        "password": "TestPass123", "phone": "8888888888"
    })
    assert res.status_code == 201
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "Rem Shop"})
    assert res.status_code == 201
    business_id = res.json()["business_id"]

    res = client.post(f"/business/customers/{business_id}", json={
        "name": "Debtor", "phone": "0555555555", "email": "debtor@test.com"
    })
    assert res.status_code == 200, res.text
    customer_id = res.json()["customer_id"]

    res = client.post(f"/debts/add_debt/{business_id}/{customer_id}", json={
        "amount": 250.0, "note": "goods on credit", "due_date": "2026-09-01"
    })
    assert res.status_code == 200, res.text
    debt_id = res.json()["debt_id"]

    return admin_token, business_id, customer_id, debt_id


def _client(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_reminders_crud_and_bodyless_get(session):
    client = _client(session)

    admin_token, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)
    client.headers["Authorization"] = f"Bearer {admin_token}"

    reminder_date = (date.today() + timedelta(days=1)).isoformat()

    # Empty note must be accepted (frontend sends note.trim() which can be "")
    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id,
        "customer_id": customer_id,
        "date": reminder_date,
        "time_of_day": "09:00",
        "note": "",
    })
    assert res.status_code == 200, res.text
    reminder_id = res.json()["reminder_id"]

    # GET with NO body must NOT 422 (regression: body was previously required)
    # and must not 500 (regression: None >= date.today() raised TypeError).
    res = client.get(f"/debts/reminders/{business_id}")
    assert res.status_code == 200, res.text
    reminders = res.json()
    assert len(reminders) == 1
    assert reminders[0]["note"] == ""
    assert reminders[0]["date"] == reminder_date
    assert reminders[0]["time_of_day"] == "09:00:00"

    # GET with an empty body still works
    res = client.request("GET", f"/debts/reminders/{business_id}", json={})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1

    # Toggle active via PUT
    res = client.put(f"/debts/reminders/{business_id}/{reminder_id}", json={"is_active": False})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    # is_active=False must actually filter, not be silently ignored
    res = client.request("GET", f"/debts/reminders/{business_id}", json={"is_active": False})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1

    res = client.request("GET", f"/debts/reminders/{business_id}", json={"is_active": True})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 0

    # Edit note + date
    edited_date = (date.today() + timedelta(days=5)).isoformat()
    res = client.put(f"/debts/reminders/{business_id}/{reminder_id}", json={
        "note": "updated note",
        "date": edited_date,
    })
    assert res.status_code == 200, res.text
    assert res.json()["note"] == "updated note"
    assert res.json()["date"] == edited_date

    # Delete
    res = client.delete(f"/debts/reminders/{business_id}/{reminder_id}")
    assert res.status_code == 200, res.text

    res = client.request("GET", f"/debts/reminders/{business_id}", json={})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 0

    app.dependency_overrides.clear()


def test_reminder_date_validation(session):
    """Regression: the guard read `post.date >= date.today()`, which rejected
    every future date and accepted every past one -- the inverse of its message."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    def post_reminder(reminder_date):
        return client.post(f"/debts/reminders/{business_id}", json={
            "debt_id": debt_id,
            "customer_id": customer_id,
            "date": reminder_date,
            "time_of_day": "09:00",
            "note": "please pay",
        })

    # Today is allowed -- the dispatcher fires on exactly this date.
    res = post_reminder(date.today().isoformat())
    assert res.status_code == 200, res.text
    reminder_id = res.json()["reminder_id"]

    # The future is allowed; this is the whole point of scheduling ahead.
    res = post_reminder((date.today() + timedelta(days=30)).isoformat())
    assert res.status_code == 200, res.text

    # The past is rejected.
    res = post_reminder((date.today() - timedelta(days=1)).isoformat())
    assert res.status_code == 403, res.text

    res = post_reminder("2020-01-01")
    assert res.status_code == 403, res.text

    # date is required by the schema.
    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id, "customer_id": customer_id, "note": "no date",
    })
    assert res.status_code == 422, res.text

    # An existing reminder cannot be edited into a dead past date either.
    res = client.put(
        f"/debts/reminders/{business_id}/{reminder_id}",
        json={"date": (date.today() - timedelta(days=2)).isoformat()},
    )
    assert res.status_code == 403, res.text

    app.dependency_overrides.clear()


def test_reminder_rejects_paid_debt(session):
    """A reminder on a settled debt can never fire, so refuse it up front."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    async def _mark_paid():
        await session.execute(
            update(dm.Debt).where(dm.Debt.debt_id == debt_id).values(is_paid=True)
        )
        await session.commit()
    asyncio.run(_mark_paid())

    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id,
        "customer_id": customer_id,
        "date": (date.today() + timedelta(days=2)).isoformat(),
        "note": "already settled",
    })
    assert res.status_code == 400, res.text

    app.dependency_overrides.clear()


def test_reminder_date_stored_as_utc_midnight(session):
    """The dispatcher truncates with func.date(Reminders.date). If the stored
    value is not midnight UTC, the truncation can land on the wrong day and the
    reminder never matches. Assert on the UTC wall clock: SQLite drops tzinfo
    on read, Postgres keeps it."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    target = date.today() + timedelta(days=3)
    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id,
        "customer_id": customer_id,
        "date": target.isoformat(),
        "note": "tz check",
    })
    assert res.status_code == 200, res.text
    reminder_id = res.json()["reminder_id"]

    async def _stored():
        return (await session.execute(
            select(dm.Reminders).where(dm.Reminders.reminder_id == reminder_id)
        )).scalar_one()

    stored = asyncio.run(_stored())
    as_utc = stored.date if stored.date.tzinfo is None else stored.date.astimezone(timezone.utc)
    assert (as_utc.year, as_utc.month, as_utc.day) == (target.year, target.month, target.day)
    assert (as_utc.hour, as_utc.minute, as_utc.second) == (0, 0, 0)

    app.dependency_overrides.clear()


def test_get_reminders_filters(session):
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    soon = (date.today() + timedelta(days=1)).isoformat()
    later = (date.today() + timedelta(days=10)).isoformat()

    for reminder_date, note in ((soon, "first"), (later, "second")):
        res = client.post(f"/debts/reminders/{business_id}", json={
            "debt_id": debt_id,
            "customer_id": customer_id,
            "date": reminder_date,
            "time_of_day": "09:00",
            "note": note,
        })
        assert res.status_code == 200, res.text

    def get(body):
        res = client.request("GET", f"/debts/reminders/{business_id}", json=body)
        assert res.status_code == 200, res.text
        return res.json()

    assert len(get({})) == 2
    assert len(get({"debt_id": debt_id})) == 2
    assert len(get({"customer_id": customer_id})) == 2

    # A date filter means "on or after", so a past date returns everything.
    assert len(get({"date": (date.today() - timedelta(days=1)).isoformat()})) == 2
    # and a future date returns only the reminder at or after it.
    assert len(get({"date": later})) == 1

    assert len(get({"note": "first"})) == 1
    assert len(get({"note": "nope"})) == 0

    assert len(get({"time_of_day": "09:00:00"})) == 2
    assert len(get({"time_of_day": "17:30:00"})) == 0

    assert len(get({"customer_id": 99999})) == 0

    app.dependency_overrides.clear()
