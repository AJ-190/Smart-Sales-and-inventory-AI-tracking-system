import os
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from src.auth import dependencies as auth_deps
from src.auth.utils import verify_token
from src.db.database import get_async_session_maker
from src.db.redis import check_jti_blocked
from src.businesses.service import business_authorized_access


def _extract_business_id(path: str):
    """Pull the owning business out of `chat/<business_id>/<file>`."""
    for segment in path.replace("\\", "/").split("/"):
        if segment.isdigit():
            return int(segment)
    return None


def _extract_token(request: Request):
    """Bearer header first, query param second."""
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.query_params.get("token")


class ProtectedStaticFiles(StaticFiles):
    """StaticFiles that only serves a file to members of the owning business."""

    def __init__(self, *args, **kwargs):
        self.session_maker = kwargs.pop("session_maker", None)
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope):
        request = Request(scope)
        response = await self._authorize(request, path)
        if response is not None:
            return response
        return await super().get_response(path, scope)

    async def _authorize(self, request: Request, path: str):
        business_id = _extract_business_id(path)
        if business_id is None:
            return self._deny(403, "Forbidden")

        token = _extract_token(request)
        if not token:
            return self._deny(401, "Not authenticated")

        try:
            token_data = verify_token(token)
        except HTTPException as exc:
            return self._deny(exc.status_code, exc.detail)

        if token_data.get("refresh"):
            return self._deny(401, "Access token is required")

        redis = getattr(request.app.state, "redis", None)
        if redis is not None and await check_jti_blocked(redis, token_data["jti"]):
            return self._deny(401, "Invalid token")

        maker = self.session_maker or get_async_session_maker
        async with maker() as session:
            try:
                current_user = await auth_deps.get_current_user(
                    token_data=token_data, session=session
                )
                await business_authorized_access(current_user, business_id, session)
            except HTTPException as exc:
                return self._deny(exc.status_code, exc.detail)

        return None

    @staticmethod
    def _deny(status_code: int, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None,
        )