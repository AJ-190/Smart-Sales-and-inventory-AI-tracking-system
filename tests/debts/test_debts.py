import asyncio
from datetime import date, datetime, timedelta, timezone
import pytest
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


def test_reminders_survive_deleted_debt_and_customer(session):
    """reminders.debt_id and customer_id are ON DELETE SET NULL and note is
    nullable, so a reminder outlives the debt it points at. The listing is
    scoped by business_id, which is what keeps the row reachable once its
    siblings are gone.

    Regression: the response schema declared debt_id, customer_id and note as
    required, so serializing an orphaned reminder raised and the endpoint 500d.
    """
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id,
        "customer_id": customer_id,
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "note": "will be orphaned",
    })
    assert res.status_code == 200, res.text
    reminder_id = res.json()["reminder_id"]

    async def _orphan():
        await session.execute(
            update(dm.Reminders)
            .where(dm.Reminders.reminder_id == reminder_id)
            .values(debt_id=None, customer_id=None, note=None)
        )
        await session.commit()

    asyncio.run(_orphan())

    res = client.get(f"/debts/reminders/{business_id}")
    assert res.status_code == 200, res.text
    orphaned = [r for r in res.json() if r["reminder_id"] == reminder_id]
    assert len(orphaned) == 1
    assert orphaned[0]["business_id"] == business_id
    assert orphaned[0]["debt_id"] is None
    assert orphaned[0]["customer_id"] is None
    assert orphaned[0]["note"] is None
    assert orphaned[0]["status"] == "pending"

    app.dependency_overrides.clear()


def test_transactions_survive_deleted_debt_and_performer(session):
    """transactions.debt_id and performer_id are ON DELETE SET NULL. Deleting a
    sale nulls the debt_id of every transaction on it, so the customer
    transaction feed has to keep rendering those rows (regression: required int
    fields raised on read)."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 100.0,
        "note": "part payment",
    })
    assert res.status_code == 200, res.text

    res = client.get(f"/debts/customer_transactions/{business_id}/{customer_id}")
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 2
    paid = next(
        r["transactions"] for r in rows if float(r["transactions"]["amount_paid"]) == 100.0
    )
    assert paid["debt_id"] is not None
    assert paid["performer_id"] is not None

    async def _orphan():
        await session.execute(
            update(dm.Transactions).values(debt_id=None, performer_id=None)
        )
        await session.commit()

    asyncio.run(_orphan())

    res = client.get(f"/debts/customer_transactions/{business_id}/{customer_id}")
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 2
    for row in rows:
        assert row["transactions"]["debt_id"] is None
        assert row["transactions"]["performer_id"] is None


def test_partial_payment_reduces_debt_exactly(session):
    """debts.amount is Numeric(12, 2) and reads back as Decimal, while
    UpdateDebt.amount arrives as a float. Mixing them raised TypeError, so every
    partial payment 500d and a customer could only ever be settled in full."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    async def _outstanding():
        return (await session.execute(
            select(dm.Debt).where(dm.Debt.debt_id == debt_id)
        )).scalar_one()

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 100.25,
        "note": "part payment",
    })
    assert res.status_code == 200, res.text

    debt = asyncio.run(_outstanding())
    assert debt.is_paid is False
    assert float(debt.amount) == 149.75
    assert float(debt.amount) == pytest.approx(250.0 - 100.25)

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 49.75,
    })
    assert res.status_code == 200, res.text

    debt = asyncio.run(_outstanding())
    assert debt.is_paid is False
    assert float(debt.amount) == pytest.approx(100.0)

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 100.0,
    })
    assert res.status_code == 200, res.text

    debt = asyncio.run(_outstanding())
    assert debt.is_paid is True
    assert float(debt.amount) == 0.0

    res = client.get(f"/debts/customer_transactions/{business_id}/{customer_id}")
    assert res.status_code == 200, res.text
    total_paid = sum(float(r["transactions"]["amount_paid"]) for r in res.json())
    assert total_paid == pytest.approx(250.0)

    app.dependency_overrides.clear()


def test_payment_larger_than_debt_settles_without_overshoot(session):
    """Paying more than the outstanding balance must clamp to the balance rather
    than drive the column negative or add a phantom overpayment."""
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    async def _outstanding():
        return (await session.execute(
            select(dm.Debt).where(dm.Debt.debt_id == debt_id)
        )).scalar_one()

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 9999.0,
    })
    assert res.status_code == 200, res.text

    debt = asyncio.run(_outstanding())
    assert debt.is_paid is True
    assert float(debt.amount) == 0.0

    res = client.get(f"/debts/customer_transactions/{business_id}/{customer_id}")
    assert res.status_code == 200, res.text
    total_paid = sum(float(r["transactions"]["amount_paid"]) for r in res.json())
    assert total_paid == pytest.approx(250.0)

    app.dependency_overrides.clear()


def test_fully_paid_flag_settles_the_balance(session):
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    async def _outstanding():
        return (await session.execute(
            select(dm.Debt).where(dm.Debt.debt_id == debt_id)
        )).scalar_one()

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "fully_paid": True,
    })
    assert res.status_code == 200, res.text

    debt = asyncio.run(_outstanding())
    assert debt.is_paid is True
    assert float(debt.amount) == 0.0

    app.dependency_overrides.clear()


def test_non_positive_payment_is_rejected(session):
    client = _client(session)

    _, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": 0,
    })
    assert res.status_code == 403, res.text

    res = client.put(f"/debts/update_customer_debt/{business_id}/{customer_id}", json={
        "amount": -50.0,
    })
    assert res.status_code == 403, res.text

    app.dependency_overrides.clear()
