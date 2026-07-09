from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from src.auth.utils import verify_token


async def auth_middleware(request: Request, call_next):
    EXCLUDED_PREFIXES = ["/public", "/auth/login", "/users/sign_up"]
    
    if request.url.path == "/" or any(request.url.path.startswith(p) for p in EXCLUDED_PREFIXES):
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