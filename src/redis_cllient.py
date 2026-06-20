import redis.asyncio as aioredis
from typing import AsyncGenerator


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    redis = aioredis.from_url("redis://localhost:6379", decode_reponses=True)
    async with redis as r:
        yield r
        
        
