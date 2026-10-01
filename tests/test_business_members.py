import asyncio
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.db.database import get_db
from src.main import app


def test_update_member_role(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin4", "email": "admin_member_role@gmail.com",
        "password": "TestPass123", "phone": "6000000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "Role Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Role Member", "email": "role_member@gmail.com",
        "password": "TestPass123", "phone": "6000000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    assert member is not None
    member_id = member.member_id

    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"role": "manager"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "manager"
    assert data["member_id"] == member_id

    app.dependency_overrides.clear()


def test_update_member_deactivate(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin5", "email": "admin_member_deact@gmail.com",
        "password": "TestPass123", "phone": "6100000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "Deact Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Deact Member", "email": "deact_member@gmail.com",
        "password": "TestPass123", "phone": "6100000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"is_active": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_active"] is False

    app.dependency_overrides.clear()


def test_update_member_role_and_active(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin6", "email": "admin_member_both@gmail.com",
        "password": "TestPass123", "phone": "6200000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "Both Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Both Member", "email": "both_member@gmail.com",
        "password": "TestPass123", "phone": "6200000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"role": "admin", "is_active": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "admin"
    assert data["is_active"] is False

    app.dependency_overrides.clear()


def test_update_member_unauthorized(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin7", "email": "admin_member_unauth@gmail.com",
        "password": "TestPass123", "phone": "6300000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "Unauth Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Unauth Member", "email": "unauth_member@gmail.com",
        "password": "TestPass123", "phone": "6300000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    client.headers["Authorization"] = f"Bearer {user_token}"
    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"role": "admin"}
    )
    assert res.status_code == 403

    app.dependency_overrides.clear()


def test_update_member_not_found(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin8", "email": "admin_member_notfound@gmail.com",
        "password": "TestPass123", "phone": "6400000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "NotFound Test Shop"})
    business_id = res.json()["business_id"]

    res = client.put(
        f"/businesses/{business_id}/members/9999",
        json={"role": "manager"}
    )
    assert res.status_code == 404

    app.dependency_overrides.clear()


def test_update_member_invalid_role(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin9", "email": "admin_member_invalid@gmail.com",
        "password": "TestPass123", "phone": "6500000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "InvalidRole Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "InvalidRole Member", "email": "invalidrole_member@gmail.com",
        "password": "TestPass123", "phone": "6500000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"role": "superuser"}
    )
    assert res.status_code == 400
    assert "Invalid role" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_update_member_wrong_business(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin10", "email": "admin_member_wrongbiz@gmail.com",
        "password": "TestPass123", "phone": "6600000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "WrongBiz Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "WrongBiz Member", "email": "wrongbiz_member@gmail.com",
        "password": "TestPass123", "phone": "6600000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.put(
        f"/businesses/9999/members/{member_id}",
        json={"role": "manager"}
    )
    assert res.status_code == 404

    app.dependency_overrides.clear()


def test_update_member_no_auth(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin11", "email": "admin_member_noauth@gmail.com",
        "password": "TestPass123", "phone": "6700000000"
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": "NoAuth Test Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "NoAuth Member", "email": "noauth_member@gmail.com",
        "password": "TestPass123", "phone": "6700000001"
    })
    user_id = res.json()["user_id"]

    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_get_member())
    member_id = member.member_id

    client.headers = {}
    res = client.put(
        f"/businesses/{business_id}/members/{member_id}",
        json={"role": "manager"}
    )
    assert res.status_code == 401

    app.dependency_overrides.clear()


def _setup_shop_with_member(client, session, *, shop, admin_email, admin_phone, member_email, member_phone, role="cashier"):
    """Sign up a super admin, open a business and approve one member into it.

    Mirrors the setup the other tests in this file do by hand; returns
    (business_id, member_id, user_id, admin_token).
    """
    res = client.post("/users/sign_up", json={
        "name": f"{shop} Admin", "email": admin_email,
        "password": "TestPass123", "phone": admin_phone
    })
    admin_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == admin_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    admin_token = auth_utils.AccessToken({"sub": str(admin_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {admin_token}"

    res = client.post("/businesses/create", json={"name": shop})
    business_id = res.json()["business_id"]
    business_key = client.get(f"/businesses/business_key/{business_id}").json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": f"{shop} Member", "email": member_email,
        "password": "TestPass123", "phone": member_phone
    })
    user_id = res.json()["user_id"]
    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {user_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join", "role": role},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    async def _get_member():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member_id = asyncio.run(_get_member()).member_id
    return business_id, member_id, user_id, admin_token


def _leave_flag(async_engine, user_id, business_id):
    """Read the soft-delete flag straight from the row.

    Uses its own session: the shared `session` fixture is reused across
    several `asyncio.run()` event loops, so a query on it can hand back a
    stale identity-map object instead of what is actually in the table.
    """
    async def _get():
        async with async_sessionmaker(bind=async_engine, expire_on_commit=False)() as s:
            result = await s.execute(
                select(um.BusinessMember).where(
                    um.BusinessMember.user_id == user_id,
                    um.BusinessMember.business_id == business_id,
                )
            )
            return result.scalar_one_or_none().leave_business
    return asyncio.run(_get())


def test_leave_business_hides_member_from_list(session, async_engine):
    """A member who left must not come back in /users/members."""
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    business_id, member_id, user_id, admin_token = _setup_shop_with_member(
        client, session,
        shop="Leave Shop", admin_email="leave_admin@gmail.com", admin_phone="6800000000",
        member_email="leave_member@gmail.com", member_phone="6800000001",
    )

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.get("/users/members")
    assert res.status_code == 200
    assert user_id in [m["user_id"] for m in res.json()]

    res = client.delete(f"/businesses/leave_business/{business_id}/{user_id}")
    assert res.status_code == 204

    # The row is kept (soft delete) ...
    assert _leave_flag(async_engine, user_id, business_id) is True

    # ... but it is no longer listed.
    res = client.get("/users/members")
    assert res.status_code == 200
    assert user_id not in [m["user_id"] for m in res.json()]

    # And it is no longer counted in the business member total.
    res = client.get(f"/businesses/{business_id}")
    assert res.status_code == 200
    assert res.json()["members"] == 1  # only the admin

    app.dependency_overrides.clear()


def test_leave_business_by_business_owner_works(session, async_engine):
    """The owner has no approval row, which used to make leave 404."""
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Owner", "email": "leave_owner@gmail.com",
        "password": "TestPass123", "phone": "6900000000"
    })
    owner_id = res.json()["user_id"]

    async def _promote():
        await session.execute(
            update(um.Users).where(um.Users.user_id == owner_id).values(role=um.RoleEnum.super_admin)
        )
        await session.commit()
    asyncio.run(_promote())

    owner_token = auth_utils.AccessToken({"sub": str(owner_id), "role": "super_admin"})
    client.headers["Authorization"] = f"Bearer {owner_token}"
    business_id = client.post("/businesses/create", json={"name": "Owner Leave Shop"}).json()["business_id"]

    res = client.delete(f"/businesses/leave_business/{business_id}/{owner_id}")
    assert res.status_code == 204
    assert _leave_flag(async_engine, owner_id, business_id) is True

    app.dependency_overrides.clear()


def test_left_member_loses_business_access(session):
    """Once gone, the leaver no longer resolves to a business or a role."""
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    business_id, member_id, user_id, admin_token = _setup_shop_with_member(
        client, session,
        shop="Access Shop", admin_email="access_admin@gmail.com", admin_phone="6910000000",
        member_email="access_member@gmail.com", member_phone="6910000001",
        role="manager",
    )
    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})

    client.headers["Authorization"] = f"Bearer {admin_token}"
    assert client.delete(f"/businesses/leave_business/{business_id}/{user_id}").status_code == 204

    # /me/profile no longer reports the business they walked away from.
    client.headers["Authorization"] = f"Bearer {user_token}"
    res = client.get("/users/me/profile")
    assert res.status_code == 200
    assert res.json()["business_id"] is None
    assert res.json()["member_id"] is None
    # The business role is gone too - it falls back to the plain user role.
    assert res.json()["role"] == "user"

    # And the business-scoped work they used to reach is now closed to them.
    assert client.get(f"/business/customers/{business_id}").status_code == 403

    app.dependency_overrides.clear()


def test_reapproved_member_returns_to_list(session):
    """Re-approving a leaver must clear the flag, otherwise rejoin is a no-op."""
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    business_id, member_id, user_id, admin_token = _setup_shop_with_member(
        client, session,
        shop="Rejoin Shop", admin_email="rejoin_admin@gmail.com", admin_phone="6920000000",
        member_email="rejoin_member@gmail.com", member_phone="6920000001",
    )
    user_token = auth_utils.AccessToken({"sub": str(user_id), "role": "user"})

    client.headers["Authorization"] = f"Bearer {admin_token}"
    assert client.delete(f"/businesses/leave_business/{business_id}/{user_id}").status_code == 204

    res = client.get("/users/members")
    assert user_id not in [m["user_id"] for m in res.json()]

    # They apply to join again and the admin approves them.
    business_key = client.get(f"/businesses/business_key/{business_id}").json()["business_key"]
    client.headers["Authorization"] = f"Bearer {user_token}"
    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Rejoin", "role": "cashier"},
    )
    assert res.status_code == 201
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200

    res = client.get("/users/members")
    assert res.status_code == 200
    assert user_id in [m["user_id"] for m in res.json()]

    app.dependency_overrides.clear()

