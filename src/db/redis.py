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


async def otp_verification(redis: airedis.Redis,  email: str, store: bool, otp: Optional[str] = None, forgot_pass: Optional[bool] = False):

    try:
        client = f"email:{email}"
        if store:
            if await redis.exists(client):
                await redis.delete(client)
            mapping = {"otp": otp or "", "forgot_pass": "1" if forgot_pass else "0"}
            await redis.hset(client, mapping=mapping)
            await redis.expire(client, 300)
            return True
        
        else:
            return await redis.hgetall(client)

    except Exception as e:
        logger.error("Failed to process otp-verification: %s", e)


async def otp_increment_attempts(redis: airedis.Redis, email: str) -> int:
    key = f"otp_attempts:{email}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 300)
    return count
