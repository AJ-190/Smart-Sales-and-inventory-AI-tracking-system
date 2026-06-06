from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import database, models, schemas
from app.core import security
import secrets, hashlib

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def create_refresh_token() -> str:
    return secrets.token_hex(64)


@router.post("/login", response_model=schemas.Token)
def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    user = (
        db.query(models.Users)
        .filter(models.Users.email == user_credentials.username)
        .first()
    )
    if not user:
        raise HTTPException(404, "User not registered")

    if not security.verify(user_credentials.password, user.password):
        raise HTTPException(401, "Incorrect password or email")

    access_token  = security.access_token({"sub": str(user.user_id), "role": user.role})
    refresh_token = create_refresh_token()


    user.refresh_token = hash_token(refresh_token)
    db.commit()

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,  
        "token_type":    "bearer"
    }


@router.post("/refresh", response_model=schemas.Token)
def refresh(
    payload: schemas.Token,
    db: Session = Depends(database.get_db)
):
    token_hash = hash_token(payload.refresh_token)

    user = (
        db.query(models.Users)
        .filter(models.Users.refresh_token == token_hash)
        .first()
    )
    if not user:
        raise HTTPException(403, "Invalid or expired refresh token")

    # Issue new tokens
    new_access_token  = security.access_token({"sub": str(user.user_id), "role": user.role})
    new_refresh_token = create_refresh_token()


    user.refresh_token = hash_token(new_refresh_token)
    db.commit()

    return {
        "access_token":  new_access_token,
        "refresh_token": new_refresh_token,
        "token_type":    "bearer"
    }


@router.post("/logout")
def logout(
    payload: schemas.Token,
    db: Session = Depends(database.get_db)
):
    token_hash = hash_token(payload.refresh_token)

    user = (
        db.query(models.Users)
        .filter(models.Users.refresh_token == token_hash)
        .first()
    )
    if user:
        user.refresh_token = None
        db.commit()

    return {"message": "Logged out successfully"}