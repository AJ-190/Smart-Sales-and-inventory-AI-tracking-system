import asyncio
import pytest
from sqlalchemy import select, update
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.database import get_db
from src.main import app


def test_update_member_role(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin4", "email": "admin_member_role@test.com",
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
        "name": "Role Member", "email": "role_member@test.com",
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
        "name": "Admin5", "email": "admin_member_deact@test.com",
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
        "name": "Deact Member", "email": "deact_member@test.com",
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
        "name": "Admin6", "email": "admin_member_both@test.com",
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
        "name": "Both Member", "email": "both_member@test.com",
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
        "name": "Admin7", "email": "admin_member_unauth@test.com",
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
        "name": "Unauth Member", "email": "unauth_member@test.com",
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
        "name": "Admin8", "email": "admin_member_notfound@test.com",
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
        "name": "Admin9", "email": "admin_member_invalid@test.com",
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
        "name": "InvalidRole Member", "email": "invalidrole_member@test.com",
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
        "name": "Admin10", "email": "admin_member_wrongbiz@test.com",
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
        "name": "WrongBiz Member", "email": "wrongbiz_member@test.com",
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
        "name": "Admin11", "email": "admin_member_noauth@test.com",
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
        "name": "NoAuth Member", "email": "noauth_member@test.com",
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
