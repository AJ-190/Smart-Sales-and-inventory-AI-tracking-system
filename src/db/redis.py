import logging
import redis
import redis.asyncio as airedis
from src.config import get_settings

logger = logging.getLogger(__name__)

async def get_redis_client() -> airedis.Redis | None:
    try:
        return airedis.from_url(get_settings().REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning("Failed to get redis client: %s", e)
        return None
        
        
async def block_jti(redis: airedis.Redis, jti: str, exp: int):
    try:
        await redis.setex(jti, exp, "revoked")
    except Exception as e:
        logger.error("Failed to block jti in redis: %s", e)
        
async def check_jti_blocked(redis: airedis.Redis, jti: str):
    try:
        return await redis.get(jti)
    except Exception as e:
        logger.error("Failed to check jti in redis: %s", e)

async def request_rate_limiter(redis: airedis.Redis, user: dict, expire: int):
    try:
        key = f"user:{user['user']['sub']}"
        data = await redis.hgetall(key)
        if data:
            count = int(data.get("count", 0))
            if count >= get_settings().REQUEST_LIMIT:
                return True
            await redis.hincrby(key, "count", 1)
            await redis.expire(key, expire)
        else:
            await redis.hset(key, mapping={"count": 1})
            await redis.expire(key, expire)
        return False
    except Exception as e:
        logger.error("Failed to check rate limit in redis: %s", e)
        return False


async def ip_rate_limiter(redis: airedis.Redis, ip: str, expire: int):
    try:
        key = f"ip:{ip}"
        data = await redis.hgetall(key)
        if data:
            count = int(data.get("count", 0))
            if count >= get_settings().REQUEST_LIMIT:
                return True
            await redis.hincrby(key, "count", 1)
            await redis.expire(key, expire)
        else:
            await redis.hset(key, mapping={"count": 1})
            await redis.expire(key, expire)
        return False
            
    except Exception as e:
        logger.error("Failed to check ip rate limit in redis: %s", e)
        return False
