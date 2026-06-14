from fastapi import APIRouter, Depends
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from src.database import get_db
from src.auth import schemas, service as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=schemas.Token)
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db)
):
    return await auth_service.login(user_credentials, db)


@router.post("/refresh", response_model=schemas.Token)
async def refresh(
    payload: schemas.Token,
    db = Depends(get_db)
):
    return await auth_service.refresh(payload, db)


@router.post("/logout")
async def logout(
    payload: schemas.Token,
    db = Depends(get_db)
):
    return await auth_service.logout(payload, db)
