from fastapi import status
from sqlalchemy import select

from src.auth import utils as auth_utils


def login(client, email="adysamuel68@gmail.com", password="passwordY123"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == status.HTTP_200_OK
    return res.json()


def test_root(client):
    res = client.get("/")
    assert res.json() == "API is running"


def test_create_user(client):
    res = client.post(
        "/users/sign_up",
        json={
            "name": "testuser",
            "email": "testuser@gmail.com",
            "password": "Testpass123",
            "phone": "0244556677"
        }
    )

    assert res.status_code == status.HTTP_201_CREATED
    new_user = res.json()
    assert new_user["email"] == "testuser@gmail.com"


def test_duplicate_email(client, test_user):
    res = client.post(
        "/users/sign_up",
        json={
            "name": "testuser2",
            "email": "adysamuel68@gmail.com",
            "password": "Testpass123",
            "phone": "0244556678"
        }
    )

    assert res.status_code == status.HTTP_409_CONFLICT


def test_login(client, test_user):
    res = client.post(
        "/auth/login",
        data={
            "username": "adysamuel68@gmail.com",
            "password": "passwordY123"
        }
    )
    assert res.status_code == status.HTTP_200_OK
    token_data = res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "Bearer"


def test_login_wrong_email(client, test_user):
    res = client.post(
        "/auth/login",
        data={
            "username": "wrong@email.com",
            "password": "passwordY123"
        }
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_login_wrong_password(client, test_user):
    res = client.post(
        "/auth/login",
        data={
            "username": "adysamuel68@gmail.com",
            "password": "wrongpassword"
        }
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_rotates_the_token(client, test_user):
    tokens = login(client)

    res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == status.HTTP_200_OK
    rotated = res.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    replay = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_accepts_the_full_pair(client, test_user):
    tokens = login(client)

    res = client.post("/auth/refresh", json=tokens)
    assert res.status_code == status.HTTP_200_OK


def test_second_login_does_not_invalidate_the_first_session(client, test_user):
    first = login(client)
    second = login(client)

    for tokens in (first, second):
        res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert res.status_code == status.HTTP_200_OK, res.json()


def test_refresh_rejects_an_access_token(client, test_user):
    tokens = login(client)

    res = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_rejects_a_tampered_token(client, test_user):
    tokens = login(client)
    tampered = tokens["refresh_token"][:-4] + "AAAA"

    res = client.post("/auth/refresh", json={"refresh_token": tampered})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_rejects_an_expired_token(client, test_user):
    tokens = login(client)
    claims = auth_utils.decode_token(tokens["refresh_token"])
    expired = auth_utils.AccessToken(
        claims["user"], expire=-1, refresh=True, sid=claims.get("sid")
    )

    res = client.post("/auth/refresh", json={"refresh_token": expired})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_is_not_accepted_as_a_bearer(client, test_user):
    tokens = login(client)

    res = client.get(
        "/businesses/my_businesses",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_without_a_body_revokes_via_the_header(client, test_user):
    tokens = login(client)

    res = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == status.HTTP_200_OK

    assert client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == status.HTTP_401_UNAUTHORIZED

    assert client.get(
        "/businesses/my_businesses",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    ).status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_with_a_body(client, test_user):
    tokens = login(client)

    res = client.post("/auth/logout", json={
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "Bearer",
    })
    assert res.status_code == status.HTTP_200_OK

    assert client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_with_no_credentials_at_all_is_a_no_op(client, test_user):
    res = client.post("/auth/logout")
    assert res.status_code == status.HTTP_200_OK


def test_logout_leaves_other_sessions_alone(client, test_user):
    first = login(client)
    second = login(client)

    res = client.post("/auth/logout", json={"refresh_token": first["refresh_token"]})
    assert res.status_code == status.HTTP_200_OK

    assert client.post(
        "/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).status_code == status.HTTP_401_UNAUTHORIZED

    assert client.post(
        "/auth/refresh", json={"refresh_token": second["refresh_token"]}
    ).status_code == status.HTTP_200_OK


def test_logout_all_sessions(client, test_user):
    first = login(client)
    second = login(client)

    res = client.post(
        "/auth/logout",
        json={"refresh_token": first["refresh_token"], "all_sessions": True},
    )
    assert res.status_code == status.HTTP_200_OK

    for tokens in (first, second):
        assert client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code == status.HTTP_401_UNAUTHORIZED


def test_login_caps_the_number_of_live_sessions(client, test_user, session):
    import asyncio

    from src.users import models as um

    tokens = [login(client) for _ in range(12)]

    def count():
        return asyncio.run(session.execute(
            select(um.RefreshSession).where(um.RefreshSession.revoked_at.is_(None))
        )).scalars().all()

    assert len(count()) <= 10

    assert client.post(
        "/auth/refresh", json={"refresh_token": tokens[-1]["refresh_token"]}
    ).status_code == status.HTTP_200_OK
