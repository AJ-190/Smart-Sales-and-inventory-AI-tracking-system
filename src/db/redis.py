import logging
import redis.asyncio as airedis
from src.config import get_settings

logger = logging.getLogger(__name__)

def get_redis_client() -> airedis.Redis | None:
    try:
        return  airedis.from_url(get_settings().REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning("Failed to get redis client")
        return None
        
        
async def block_jti(redis: airedis.Redis, jti: str, exp: int):
    try:
        await redis.setex(jti, exp, "revoked")
    except Exception as e:
        logger.info("Failed to block jti in redis")
        
async def check_jti_blocked(redis: airedis.Redis, jti: str):
    try:
        return await redis.get(jti)
    except Exception as e:
        logger.info("Failed to check jti in redis")