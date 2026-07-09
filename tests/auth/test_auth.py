from fastapi import status


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
