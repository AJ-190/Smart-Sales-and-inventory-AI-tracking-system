from fastapi import status
from unittest.mock import AsyncMock, patch


def test_get_otp_code(client):
    res = client.post(
        "/auth/otp/get_code",
        json={"email": "testuser@gmail.com"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["msg"] == "OTP-verification code is sent"


def test_get_otp_code_invalid_email(client):
    res = client.post(
        "/auth/otp/get_code",
        json={"email": "not-an-email"}
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_otp_correct_code(client, test_user):
    app = client.app
    app.state.redis.hgetall.return_value = {"otp": "1234567", "forgot_pass": "0"}

    res = client.post(
        "/auth/otp/verification",
        json={"email": "adysamuel68@gmail.com", "otp": "1234567"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["email"] == "adysamuel68@gmail.com"


def test_verify_otp_wrong_code(client, test_user):
    app = client.app
    app.state.redis.hgetall.return_value = {"otp": "1234567", "forgot_pass": "0"}

    res = client.post(
        "/auth/otp/verification",
        json={"email": "adysamuel68@gmail.com", "otp": "9999999"}
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert res.json()["detail"] == "Incorrect OTP-verification code"


def test_verify_otp_expired(client, test_user):
    app = client.app
    app.state.redis.hgetall.return_value = {}

    res = client.post(
        "/auth/otp/verification",
        json={"email": "adysamuel68@gmail.com", "otp": "1234567"}
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "expired" in res.json()["detail"]


def test_verify_otp_too_many_attempts(client, test_user):
    app = client.app
    app.state.redis.hgetall.return_value = {"otp": "1234567", "forgot_pass": "0"}
    app.state.redis.incr.return_value = 4

    res = client.post(
        "/auth/otp/verification",
        json={"email": "adysamuel68@gmail.com", "otp": "9999999"}
    )
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Too many failed attempts" in res.json()["detail"]


def test_verify_otp_missing_email(client):
    res = client.post(
        "/auth/otp/verification",
        json={"otp": "1234567"}
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_otp_missing_otp(client):
    res = client.post(
        "/auth/otp/verification",
        json={"email": "testuser@gmail.com"}
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_otp_user_not_registered(client):
    app = client.app
    app.state.redis.hgetall.return_value = {"otp": "1234567", "forgot_pass": "0"}

    res = client.post(
        "/auth/otp/verification",
        json={"email": "nonexistent@gmail.com", "otp": "1234567"}
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "User not registered"
