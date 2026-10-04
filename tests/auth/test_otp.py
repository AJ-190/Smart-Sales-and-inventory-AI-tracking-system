from fastapi import status
from unittest.mock import AsyncMock, patch

from src.auth.service import digest

EMAIL = "adysamuel68@gmail.com"


def stored(otp, email=EMAIL, forgot_pass="0"):
    """What redis holds: the keyed hash of the code, never the code itself."""
    return {"otp": digest(email, otp), "forgot_pass": forgot_pass}


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
    app.state.redis.hgetall.return_value = stored("123456")

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "123456"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["email"] == EMAIL


def test_verify_otp_wrong_code(client, test_user):
    """A wrong code must be rejected, and must not verify the account."""
    app = client.app
    app.state.redis.hgetall.return_value = stored("123456")

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "999999"}
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert res.json()["detail"] == "Incorrect OTP-verification code"
    assert res.json().get("is_verified") is not True


def test_verify_otp_plaintext_code_in_redis_does_not_verify(client, test_user):
    """Regression: only the hashed code may verify, never a plaintext match."""
    app = client.app
    app.state.redis.hgetall.return_value = {"otp": "123456", "forgot_pass": "0"}

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "123456"}
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_verify_otp_expired(client, test_user):
    app = client.app
    app.state.redis.hgetall.return_value = {}

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "123456"}
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "expired" in res.json()["detail"]


def test_verify_otp_too_many_attempts(client, test_user):
    """Past the attempt budget the record is dropped and a 429 comes back."""
    app = client.app
    app.state.redis.hgetall.return_value = stored("123456")
    app.state.redis.incr.return_value = 4

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "999999"}
    )
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Too many failed attempts" in res.json()["detail"]
    assert app.state.redis.delete.await_count >= 1


def test_verify_otp_within_attempt_budget_stays_403(client, test_user):
    """One wrong code is a 403, not a lockout."""
    from src.tasks.otp_task import MAX_OTP_ATTEMPTS

    app = client.app
    app.state.redis.hgetall.return_value = stored("123456")
    app.state.redis.incr.return_value = MAX_OTP_ATTEMPTS

    res = client.post(
        "/auth/otp/verification",
        json={"email": EMAIL, "otp": "999999"}
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_verify_otp_missing_email(client):
    res = client.post(
        "/auth/otp/verification",
        json={"otp": "123456"}
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
    app.state.redis.hgetall.return_value = stored("123456", email="nonexistent@gmail.com")

    res = client.post(
        "/auth/otp/verification",
        json={"email": "nonexistent@gmail.com", "otp": "123456"}
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "User not registered"


def test_generated_otp_is_stored_as_a_hash_not_the_code(client):
    """Redis must hold a 64-char digest, never the 6-digit code in the clear."""
    email = "otp6digits@gmail.com"
    res = client.post("/auth/otp/get_code", json={"email": email})
    assert res.status_code == status.HTTP_200_OK

    mapping = None
    for call in client.app.state.redis.hset.call_args_list:
        if call.kwargs.get("mapping") and "otp" in call.kwargs["mapping"]:
            mapping = call.kwargs["mapping"]
            break
    assert mapping is not None

    stored_value = mapping["otp"]
    assert len(stored_value) == 64
    assert all(c in "0123456789abcdef" for c in stored_value)
    assert not stored_value.isdigit()


def test_emailed_otp_is_exactly_6_digits(client):
    """The code the customer receives is a plain 6-digit number."""
    from src.tasks.otp_task import _build_otp_html

    with patch("src.tasks.otp_task._send_otp_email", new_callable=AsyncMock) as sender:
        sender.return_value = True
        res = client.post("/auth/otp/get_code", json={"email": "six@digits.com"})

    assert res.status_code == status.HTTP_200_OK
    code = sender.await_args[0][1]
    assert len(code) == 6
    assert code.isdigit()
    assert code in _build_otp_html(code)


def test_stored_digest_round_trips_through_verify(client, test_user):
    """End to end: the emailed code is what makes the stored digest verify."""
    from src.tasks.otp_task import _build_otp_html

    email = "round@trip.com"
    with patch("src.tasks.otp_task._send_otp_email", new_callable=AsyncMock) as sender:
        sender.return_value = True
        client.post("/auth/otp/get_code", json={"email": email})
    code = sender.await_args[0][1]

    app = client.app
    app.state.redis.hgetall.return_value = stored(code, email=email)

    res = client.post(
        "/auth/otp/verification",
        json={"email": email, "otp": code},
    )
    # The account is not in the DB under this address, so a valid code gets as
    # far as the user lookup before the 404 - which proves it was accepted.
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "User not registered"


def test_verify_otp_rejects_non_6_digit_code(client, test_user):
    for bad_otp in ("12345", "1234567", "abcdef", ""):
        res = client.post(
            "/auth/otp/verification",
            json={"email": "adysamuel68@gmail.com", "otp": bad_otp}
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
