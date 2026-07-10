import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status
from src.config import get_settings


@pytest.fixture
def rate_limited_redis():
    mock_redis = AsyncMock()
    request_count = {"count": 0}

    async def mock_hgetall(key):
        count = request_count["count"]
        if count > 0:
            return {"count": str(count)}
        return {}

    async def mock_hincrby(key, field, amount):
        request_count["count"] += amount
        return request_count["count"]

    async def mock_hset(key, mapping):
        request_count["count"] = mapping.get("count", 1)

    mock_redis.hgetall = AsyncMock(side_effect=mock_hgetall)
    mock_redis.hincrby = AsyncMock(side_effect=mock_hincrby)
    mock_redis.hset = AsyncMock(side_effect=mock_hset)
    mock_redis.expire = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    return mock_redis, request_count


def test_rate_limiter_allows_requests_within_limit(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    settings = get_settings()
    for i in range(settings.REQUEST_LIMIT):
        res = authorized_sup_client.get("/users/all_users")
        assert res.status_code == 200, f"Request {i+1} should succeed"


def test_rate_limiter_blocks_requests_over_limit(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    settings = get_settings()
    for _ in range(settings.REQUEST_LIMIT):
        authorized_sup_client.get("/users/all_users")

    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert res.json()["msg"] == "Too many requests, try again later"


def test_rate_limiter_returns_429_json_response(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    settings = get_settings()
    for _ in range(settings.REQUEST_LIMIT):
        authorized_sup_client.get("/users/all_users")

    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    body = res.json()
    assert "msg" in body
    assert isinstance(body["msg"], str)


def test_rate_limiter_uses_correct_redis_key(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    authorized_sup_client.get("/users/all_users")

    expected_key = f"user:{test_user.user_id}"
    mock_redis.hgetall.assert_called_with(expected_key)


def test_rate_limiter_sets_expiry(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    authorized_sup_client.get("/users/all_users")

    expected_key = f"user:{test_user.user_id}"
    settings = get_settings()
    mock_redis.expire.assert_called_with(expected_key, settings.REQUEST_LIMIT_EXPIRY)


def test_rate_limiter_initializes_new_user(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    mock_redis.hgetall = AsyncMock(return_value={})
    authorized_sup_client.app.state.redis = mock_redis

    authorized_sup_client.get("/users/all_users")

    expected_key = f"user:{test_user.user_id}"
    mock_redis.hset.assert_called_once_with(expected_key, mapping={"count": 1})


def test_rate_limiter_increments_existing_count(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    request_count["count"] = 2
    authorized_sup_client.app.state.redis = mock_redis

    authorized_sup_client.get("/users/all_users")

    expected_key = f"user:{test_user.user_id}"
    mock_redis.hincrby.assert_called_with(expected_key, "count", 1)


def test_rate_limiter_uses_configured_limit(authorized_sup_client, test_user, rate_limited_redis):
    mock_redis, request_count = rate_limited_redis
    authorized_sup_client.app.state.redis = mock_redis

    settings = get_settings()
    request_count["count"] = settings.REQUEST_LIMIT - 1

    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == 200

    request_count["count"] = settings.REQUEST_LIMIT
    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_rate_limiter_handles_redis_error_gracefully(authorized_sup_client, test_user):
    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(side_effect=Exception("Redis connection failed"))
    mock_redis.get = AsyncMock(return_value=None)
    authorized_sup_client.app.state.redis = mock_redis

    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == 200
