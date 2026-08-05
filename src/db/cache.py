from functools import wraps
from typing import Optional, Any, Callable, Awaitable
from redis.asyncio import Redis
import enum
import json
from fastapi import HTTPException, status



class CacheKey(str, enum.Enum):
    GET_DEBTS = "get_debts"
    GET_CUSTOMERS_WITH_DEBT = "get_customers_with_debt"
    GET_CUSTOMER_WITH_DEBT = "get_customer_with_debt"
    GET_CUSTOMER_TRANSACTIONS = "get_customer_transactions"
    GET_CUSTOMER_BY_ID = "get_customer_by_id"
    GET_CUSTOMERS = "get_customers"
    GET_SALES = "get_sales"
    GET_SALE_BY_ID = "get_sale_by_id"
    GET_SALE_ITEMS = "get_sale_items"
    GET_SALE_ITEM_BY_ID = "get_sale_item_by_id"
    GET_BUSINESS_MEMBERS = "get_business_members"
    GET_BUSINESS_MEMBER_BY_ID = "get_business_member_by_id"


def build_keys(base: CacheKey, **kwargs):
    parts = [base.value]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    return ":".join(parts)



class CacheManager:
    def __init__(self, redis_client: Redis) -> Optional[Any]:
        self.redis = redis_client
        
        
    async def get(self, key: str) -> Optional[Any]:
        data =  await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def set(self,key: str, data: Any, expire: int = 3600) -> json.loads:
        await self.redis.set(key, json.dumps(data), ex=expire)
        return data
    
    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def delete_by_pattern(self, pattern: str) -> None:
        async for key in self.redis.scan_iter(f"{pattern}*"):
            await self.redis.delete(key)
        
        
        
def cache(key_builder: Callable[..., Awaitable[Any]], ttl: Optional[int]= 300) -> None:
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_service: CacheManager = kwargs.get("cache")
            
            
            key = key_builder(*args, **kwargs)
            if key is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cache key could not be built")
            cache_data = await func.get(key)
            if cache_data is not None:
                return cache_data
            result = await cache_service.get(*args, **kwargs)
            data = cache_service.set(key, result, ttl)
            return data
        return wrapper
    return decorator
            
             
                
        