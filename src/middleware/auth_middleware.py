from fastapi import Request, status
from fastapi.responses import JSONResponse
from src.db.redis import ip_rate_limiter
from src.config import get_settings
from src.middleware.logging import logger


logger = logger("auth_middleware")


def _log_request(request: Request, **kwargs):
    
    context = {
        "request_id": request.headers.get("X-Request-ID"),
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
        "method": request.method,
        "query_params": str(request.query_params) if request.query_params else None
    }
    context.update(kwargs)
    return context

RATE_LIMITED_ROUTES = ["/auth/login", "/users/sign_up"]

async def auth_middleware(request: Request, call_next):
    
    if request.url.path in RATE_LIMITED_ROUTES:
        client_ip = request.client.host
        if await ip_rate_limiter(request.app.state.redis, client_ip, get_settings().REQUEST_LIMIT_EXPIRY):
            
            logger.debug("Rate limiting exceeded", 
                         extra=_log_request(request, status_code=status.HTTP_429_TOO_MANY_REQUESTS))
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"msg": "Too many requests, try again later"}
            )
        
            
    
    response = await call_next(request)
    return response
