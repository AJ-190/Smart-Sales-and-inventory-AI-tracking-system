import asyncio
from sqlalchemy import select, update
from src.businesses import models as bm
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.database import get_db
from src.main import app


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


def test_reminders_crud_and_bodyless_get(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    admin_token, business_id, customer_id, debt_id = _setup_business_with_debt(client, session)
    client.headers["Authorization"] = f"Bearer {admin_token}"

    # Empty note must be accepted (frontend sends note.trim() which can be "")
    res = client.post(f"/debts/reminders/{business_id}", json={
        "debt_id": debt_id,
        "customer_id": customer_id,
        "start_date": "2026-08-25",
        "end_date": "2026-09-01",
        "time_of_day": "09:00",
        "note": "",
    })
    assert res.status_code == 200, res.text
    reminder_id = res.json()["reminder_id"]

    # GET with NO body must NOT 422 (regression: body was previously required)
    res = client.get(f"/debts/reminders/{business_id}")
    assert res.status_code == 200, res.text
    reminders = res.json()
    assert len(reminders) == 1
    assert reminders[0]["note"] == ""
    assert reminders[0]["start_date"] == "2026-08-25"
    assert reminders[0]["time_of_day"] == "09:00:00"

    # GET with a body still works
    res = client.request("GET", f"/debts/reminders/{business_id}", json={})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1

    # Toggle active via PUT
    res = client.put(f"/debts/reminders/{business_id}/{reminder_id}", json={"is_active": False})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    # Edit note + dates
    res = client.put(f"/debts/reminders/{business_id}/{reminder_id}", json={
        "note": "updated note",
        "start_date": "2026-08-26",
        "end_date": "2026-09-02",
    })
    assert res.status_code == 200, res.text
    assert res.json()["note"] == "updated note"
    assert res.json()["start_date"] == "2026-08-26"

    # Delete
    res = client.delete(f"/debts/reminders/{business_id}/{reminder_id}")
    assert res.status_code == 200, res.text

    res = client.request("GET", f"/debts/reminders/{business_id}", json={})
    assert res.status_code == 200, res.text
    assert len(res.json()) == 0

    app.dependency_overrides.clear()
