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


def test_rate_limiter_handles_redis_error_gracefully(authorized_sup_client, test_user):
    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(side_effect=Exception("Redis connection failed"))
    mock_redis.get = AsyncMock(return_value=None)
    authorized_sup_client.app.state.redis = mock_redis

    res = authorized_sup_client.get("/users/all_users")
    assert res.status_code == 200
