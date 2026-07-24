import asyncio
import pytest
from sqlalchemy import select, update
from src.businesses import schemas, models as bm
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.database import get_db
from src.main import app


def test_approval_creates_business_member(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin", "email": "admin_approval@test.com",
        "password": "TestPass123", "phone": "0000000000"
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

    res = client.post("/businesses/create", json={"name": "Test Shop"})
    assert res.status_code == 201
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    assert res.status_code == 200
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Requester", "email": "req_approval@test.com",
        "password": "TestPass123", "phone": "1111111111"
    })
    assert res.status_code == 201
    requester_id = res.json()["user_id"]

    requester_token = auth_utils.AccessToken({"sub": str(requester_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {requester_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as cashier", "role": "cashier"},
    )
    assert res.status_code == 201
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    async def _check():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == requester_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_check())

    assert member is not None
    assert member.role == um.RoleEnum.cashier
    assert member.is_active is True

    app.dependency_overrides.clear()


def test_reject_does_not_create_business_member(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin2", "email": "admin_reject@test.com",
        "password": "TestPass123", "phone": "2222222222"
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

    res = client.post("/businesses/create", json={"name": "Reject Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Requester2", "email": "req_reject@test.com",
        "password": "TestPass123", "phone": "3333333333"
    })
    requester_id = res.json()["user_id"]

    requester_token = auth_utils.AccessToken({"sub": str(requester_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {requester_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as manager", "role": "manager"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 0},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    async def _check():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == requester_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_check())
    assert member is None

    app.dependency_overrides.clear()


def test_approve_sets_correct_role(session):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    res = client.post("/users/sign_up", json={
        "name": "Admin3", "email": "admin_role@test.com",
        "password": "TestPass123", "phone": "4444444444"
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

    res = client.post("/businesses/create", json={"name": "Role Shop"})
    business_id = res.json()["business_id"]

    res = client.get(f"/businesses/business_key/{business_id}")
    business_key = res.json()["business_key"]

    res = client.post("/users/sign_up", json={
        "name": "Requester3", "email": "req_role@test.com",
        "password": "TestPass123", "phone": "5555555555"
    })
    requester_id = res.json()["user_id"]

    requester_token = auth_utils.AccessToken({"sub": str(requester_id), "role": "user"})
    client.headers["Authorization"] = f"Bearer {requester_token}"

    res = client.post(
        "/businesses/approvals/send_approval",
        json={"business_key": business_key, "reason": "Join as manager", "role": "manager"},
    )
    approval_id = res.json()["approval_id"]

    client.headers["Authorization"] = f"Bearer {admin_token}"
    res = client.post(
        f"/businesses/approvals/confirm_approvals/{business_id}",
        json={"approval_id": approval_id, "dir": 1},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    async def _check():
        result = await session.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.user_id == requester_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        return result.scalar_one_or_none()

    member = asyncio.run(_check())
    assert member is not None
    assert member.role == um.RoleEnum.manager

    app.dependency_overrides.clear()
