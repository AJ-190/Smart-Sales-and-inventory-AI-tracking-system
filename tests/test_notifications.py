"""
Notification read-state and deletion.

Covers:
1. list is scoped to the requesting user (was a cross-user data leak)
2. list includes `title` (was stripped by the response model)
3. mark-as-read, mark-all-read
4. delete single, clear read
5. one user cannot read/delete another user's notification
"""
import asyncio
import pytest

from src.users import models as um
from src.businesses import models as bm
from src.notifications.models import Notification
from src.auth import utils as auth_utils


def _make_user(session, email, role=um.RoleEnum.cashier):
    user = um.Users(
        name=email.split("@")[0],
        email=email,
        password=auth_utils.hash("passwordY123"),
        phone="0257524704",
        role=role,
        is_verified=True,
    )

    async def _create():
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return asyncio.run(_create())


def _make_business(session):
    business = bm.Business(name="Kwame Shop")

    async def _create():
        session.add(business)
        await session.commit()
        await session.refresh(business)
        return business

    return asyncio.run(_create())


def _notify(session, business_id, user_id, title="Low stock", message="Rice is running out"):
    n = Notification(
        business_id=business_id,
        user_id=user_id,
        title=title,
        message=message,
    )

    async def _create():
        session.add(n)
        await session.commit()
        await session.refresh(n)
        return n

    return asyncio.run(_create())


def _client_for(session, user):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.db.database import get_db

    def overrides_get_db():
        yield session

    app.dependency_overrides[get_db] = overrides_get_db
    c = TestClient(app)
    token = auth_utils.AccessToken({"sub": str(user.user_id), "role": user.role})
    c.headers = {"Authorization": f"Bearer {token}"}
    return c


@pytest.fixture
def alice(session):
    return _make_user(session, "alice@example.com")


@pytest.fixture
def bob(session):
    return _make_user(session, "bob@example.com")


@pytest.fixture
def shop(session):
    return _make_business(session)


def test_list_is_scoped_to_the_requesting_user(session, alice, bob, shop):
    """Regression: list used to return every notification in the business."""
    mine = _notify(session, shop.business_id, alice.user_id, title="For Alice")
    _notify(session, shop.business_id, bob.user_id, title="For Bob")

    client = _client_for(session, alice)
    res = client.get(f"/notifications/get_notifications/{shop.business_id}")

    assert res.status_code == 200
    titles = [n["title"] for n in res.json()]
    assert titles == ["For Alice"]
    assert mine.title in titles
    assert "For Bob" not in titles


def test_list_includes_title(session, alice, shop):
    """Regression: `title` was missing from the response model, so FastAPI
    stripped it from every notification."""
    _notify(session, shop.business_id, alice.user_id, title="Stock running low")

    client = _client_for(session, alice)
    res = client.get(f"/notifications/get_notifications/{shop.business_id}")

    assert res.status_code == 200
    assert res.json()[0]["title"] == "Stock running low"


def test_list_sorted_newest_first(session, alice, shop):
    _notify(session, shop.business_id, alice.user_id, title="First")
    _notify(session, shop.business_id, alice.user_id, title="Second")

    client = _client_for(session, alice)
    res = client.get(f"/notifications/get_notifications/{shop.business_id}")

    assert [n["title"] for n in res.json()] == ["Second", "First"]


def test_unread_only_filter(session, alice, shop):
    client = _client_for(session, alice)
    read = _notify(session, shop.business_id, alice.user_id, title="Already read")
    _notify(session, shop.business_id, alice.user_id, title="Unread")

    client.patch(f"/notifications/{read.notification_id}/read")
    res = client.get(f"/notifications/get_notifications/{shop.business_id}?unread_only=true")

    assert [n["title"] for n in res.json()] == ["Unread"]


def test_mark_single_read(session, alice, shop):
    n = _notify(session, shop.business_id, alice.user_id)
    client = _client_for(session, alice)

    res = client.patch(f"/notifications/{n.notification_id}/read")

    assert res.status_code == 200
    assert res.json()["is_read"] is True

    # Idempotent: a second call is still a 200.
    assert client.patch(f"/notifications/{n.notification_id}/read").status_code == 200


def test_mark_all_read(session, alice, shop):
    for _ in range(3):
        _notify(session, shop.business_id, alice.user_id)
    client = _client_for(session, alice)

    res = client.post(f"/notifications/read-all/{shop.business_id}")

    assert res.status_code == 200
    assert res.json()["updated_count"] == 3
    listing = client.get(f"/notifications/get_notifications/{shop.business_id}").json()
    assert all(n["is_read"] for n in listing)


def test_mark_all_read_leaves_other_users_alone(session, alice, bob, shop):
    _notify(session, shop.business_id, alice.user_id)
    theirs = _notify(session, shop.business_id, bob.user_id)
    client = _client_for(session, alice)

    client.post(f"/notifications/read-all/{shop.business_id}")

    owner = _client_for(session, bob)
    still = owner.get(f"/notifications/get_notifications/{shop.business_id}").json()[0]
    assert still["is_read"] is False
    assert theirs.notification_id == still["notification_id"]


def test_delete_single_notification(session, alice, shop):
    n = _notify(session, shop.business_id, alice.user_id)
    client = _client_for(session, alice)

    res = client.delete(f"/notifications/{n.notification_id}")

    assert res.status_code == 200
    assert res.json()["deleted_id"] == n.notification_id
    assert client.get(f"/notifications/get_notifications/{shop.business_id}").json() == []


def test_delete_unknown_id_is_404(session, alice, shop):
    client = _client_for(session, alice)
    assert client.delete("/notifications/999999").status_code == 404


def test_cannot_delete_another_users_notification(session, alice, bob, shop):
    """The ownership guard that makes delete safe to expose at all."""
    theirs = _notify(session, shop.business_id, bob.user_id)
    client = _client_for(session, alice)

    res = client.delete(f"/notifications/{theirs.notification_id}")

    assert res.status_code == 404
    # Still present for the owner.
    owner = _client_for(session, bob)
    ids = [n["notification_id"] for n in owner.get(f"/notifications/get_notifications/{shop.business_id}").json()]
    assert theirs.notification_id in ids


def test_cannot_mark_another_users_notification_read(session, alice, bob, shop):
    theirs = _notify(session, shop.business_id, bob.user_id)
    client = _client_for(session, alice)

    assert client.patch(f"/notifications/{theirs.notification_id}/read").status_code == 404

    owner = _client_for(session, bob)
    still = owner.get(f"/notifications/get_notifications/{shop.business_id}").json()[0]
    assert still["is_read"] is False


def test_clear_read_keeps_unread(session, alice, shop):
    client = _client_for(session, alice)
    read = _notify(session, shop.business_id, alice.user_id, title="Read one")
    _notify(session, shop.business_id, alice.user_id, title="Still unread")
    client.patch(f"/notifications/{read.notification_id}/read")

    res = client.delete(f"/notifications/read/{shop.business_id}")

    assert res.status_code == 200
    assert res.json()["deleted_count"] == 1
    remaining = [n["title"] for n in client.get(f"/notifications/get_notifications/{shop.business_id}").json()]
    assert remaining == ["Still unread"]
