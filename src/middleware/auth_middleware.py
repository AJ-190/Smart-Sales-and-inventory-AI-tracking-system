from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from src.auth.utils import verify_token
from src.db.redis import ip_rate_limiter
from src.config import get_settings

RATE_LIMITED_ROUTES = ["/auth/login", "/users/sign_up"]

async def auth_middleware(request: Request, call_next):
    EXCLUDED_PREFIXES = ["/public", "/auth/otp/verification", "/auth/otp/get_code"]
    
    if request.url.path == "/" or any(request.url.path.startswith(p) for p in EXCLUDED_PREFIXES):
        response = await call_next(request)
        return response
    
    if request.url.path in RATE_LIMITED_ROUTES:
        client_ip = request.client.host
        if await ip_rate_limiter(request.app.state.redis, client_ip, get_settings().REQUEST_LIMIT_EXPIRY):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"msg": "Too many requests, try again later"}
            )
        response = await call_next(request)
        return response
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer"):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            content={"msg": "Not Authenticated"}
        )
        
    token = auth_header.split(" ")[1]
    
    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"msg": "Not Authenticated"}
        )
    
    try:
        user = verify_token(token)
    except HTTPException:
        return JSONResponse(
            
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"msg": "Invalid or expired token"}
        )
    
    request.state.user = user
    response = await call_next(request)
    return response
