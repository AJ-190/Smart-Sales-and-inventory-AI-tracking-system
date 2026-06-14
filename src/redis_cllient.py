import redis.asyncio as aioredis
from typing import AsyncGenerator


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    r = aioredis.from_url("redis://localhost:6379", decode_reponses=True)
    
    try:
        yield r
    finally:
        await r.close()
        
        
        
