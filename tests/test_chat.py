import asyncio
import pytest
from sqlalchemy import select, func
from src.chat import models as cm
from src.users import models as um
from src.auth import utils as auth_utils
from fastapi.testclient import TestClient
from src.db.database import get_db
from src.main import app


@pytest.fixture
def chat_business(authorized_sup_client):
    res = authorized_sup_client.post("/businesses/create", json={"name": "Chat Shop"})
    assert res.status_code == 201
    return res.json()["business_id"]


@pytest.fixture
def seeded_messages(session, chat_business, test_user):
    async def _seed():
        for i in range(3):
            session.add(cm.GroupChatMessages(
                user_id=test_user.user_id,
                business_id=chat_business,
                message=f"hello {i}",
            ))
        await session.commit()

    asyncio.run(_seed())


def _client_with_token(session, token):
    def override():
        yield session
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_ws_ticket_issued_for_member(authorized_sup_client, chat_business):
    res = authorized_sup_client.post(f"/chat/ws-ticket/{chat_business}")
    assert res.status_code == 200
    data = res.json()
    assert data["ticket"]
    assert data["expires_in"] == 300


def test_ws_ticket_forbidden_for_non_member(session, chat_business):
    async def _create_user():
        session.add(um.Users(
            name="Stranger",
            email="stranger_chat@gmail.com",
            password="passwordY123",
            role=um.RoleEnum.user,
            is_verified=True,
        ))
        await session.commit()
        result = await session.execute(
            select(um.Users).where(um.Users.email == "stranger_chat@gmail.com")
        )
        return result.scalar_one()

    user = asyncio.run(_create_user())
    token = auth_utils.AccessToken({"sub": str(user.user_id), "role": "user"})
    client = _client_with_token(session, token)
    res = client.post(f"/chat/ws-ticket/{chat_business}")
    assert res.status_code == 403


def test_messages_history_empty(authorized_sup_client, chat_business):
    res = authorized_sup_client.get(f"/chat/{chat_business}/messages")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["has_more"] is False
    assert data["total"] == 0


def test_messages_history_and_read_position(authorized_sup_client, chat_business, seeded_messages):
    res = authorized_sup_client.get(f"/chat/{chat_business}/messages")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["message"] == "hello 0"
    assert data["items"][2]["message"] == "hello 2"
    assert data["items"][0]["name"] == "Addy"

    ids = [m["id"] for m in data["items"]]
    newest_id = max(ids)

    res = authorized_sup_client.get(f"/chat/{chat_business}/unread_count")
    assert res.status_code == 200
    assert res.json()["unread"] == 3

    res = authorized_sup_client.put(
        f"/chat/{chat_business}/read_position",
        json={"last_read_message_id": newest_id},
    )
    assert res.status_code == 200
    assert res.json()["last_read_message_id"] == newest_id

    res = authorized_sup_client.get(f"/chat/{chat_business}/unread_count")
    assert res.json()["unread"] == 0


def test_edit_message(authorized_sup_client, chat_business, seeded_messages):
    history = authorized_sup_client.get(f"/chat/{chat_business}/messages").json()
    msg_id = history["items"][0]["id"]

    res = authorized_sup_client.put(
        f"/chat/{chat_business}/messages/{msg_id}",
        json={"message": "edited text"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "edited text"
    assert data["is_edited"] is True

    history = authorized_sup_client.get(f"/chat/{chat_business}/messages").json()
    updated = next(m for m in history["items"] if m["id"] == msg_id)
    assert updated["message"] == "edited text"


def test_edit_message_forbidden_for_other_user(session, chat_business, seeded_messages, test_user):
    # A non-member second user cannot edit someone else's message
    async def _create_user():
        session.add(um.Users(
            name="Bob",
            email="bob_chat@gmail.com",
            password="passwordY123",
            role=um.RoleEnum.user,
            is_verified=True,
        ))
        await session.commit()
        result = await session.execute(
            select(um.Users).where(um.Users.email == "bob_chat@gmail.com")
        )
        return result.scalar_one()

    user = asyncio.run(_create_user())
    token = auth_utils.AccessToken({"sub": str(user.user_id), "role": "user"})
    client = _client_with_token(session, token)

    owner_token = auth_utils.AccessToken({"sub": str(test_user.user_id), "role": "super_admin"})
    history_res = _client_with_token(session, owner_token).get(
        f"/chat/{chat_business}/messages"
    )
    msg_id = history_res.json()["items"][0]["id"]

    res = client.put(f"/chat/{chat_business}/messages/{msg_id}", json={"message": "hijack"})
    assert res.status_code == 403


def test_delete_message(authorized_sup_client, chat_business, seeded_messages):
    history = authorized_sup_client.get(f"/chat/{chat_business}/messages").json()
    msg_id = history["items"][1]["id"]

    res = authorized_sup_client.delete(f"/chat/{chat_business}/messages/{msg_id}")
    assert res.status_code == 200
    assert res.json()["is_deleted"] is True

    history = authorized_sup_client.get(f"/chat/{chat_business}/messages").json()
    remaining = [m for m in history["items"] if m["id"] == msg_id]
    assert remaining == []
    assert history["total"] == 2


def test_upload_attachment(authorized_sup_client, chat_business):
    res = authorized_sup_client.post(
        f"/chat/{chat_business}/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["attachment_name"] == "notes.txt"
    assert data["attachment_type"] == "text/plain"
    assert data["attachment_size"] == 11
    assert data["attachment_url"].startswith("/media/chat/")


def test_upload_attachment_rejects_bad_type(authorized_sup_client, chat_business):
    res = authorized_sup_client.post(
        f"/chat/{chat_business}/upload",
        files={"file": ("evil.exe", b"\x00" * 10, "application/octet-stream")},
    )
    assert res.status_code == 400