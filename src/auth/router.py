from fastapi import APIRouter, Depends
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth import schemas, service as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=schemas.Token)
def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return auth_service.login(user_credentials, db)


@router.post("/refresh", response_model=schemas.Token)
def refresh(
    payload: schemas.Token,
    db: Session = Depends(get_db)
):
    return auth_service.refresh(payload, db)


@router.post("/logout")
def logout(
    payload: schemas.Token,
    db: Session = Depends(get_db)
):
    return auth_service.logout(payload, db)
