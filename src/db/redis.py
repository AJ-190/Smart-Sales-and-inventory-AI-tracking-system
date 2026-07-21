import logging
import redis
import redis.asyncio as airedis
from src.config import get_settings
from typing import Optional

logger = logging.getLogger(__name__)

async def get_redis_client() -> airedis.Redis | None:
    url = get_settings().REDIS_URL
    if not url:
        print("[REDIS] REDIS_URL is not set")
        return None
    try:
        client = airedis.from_url(url, decode_responses=True)
        await client.ping()
        print("[REDIS] Connected successfully")
        return client
    except Exception as e:
        print(f"[REDIS] Failed to connect: {e}")
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


async def otp_verification(redis: airedis.Redis,  email: str, store: bool, otp: Optional[str] = None):
    client = f"email:{email}"
    if store:
        if await redis.get(client):
            await redis.delete(client)
        await redis.setex(client, 300, otp)
    else:
        otp_ = await redis.get(client)
        await redis.delete(client)
        if otp_ is None:
            return None
        return otp_
