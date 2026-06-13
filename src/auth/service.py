import secrets
import hashlib
from fastapi import status, HTTPException, Depends
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.database import get_db
from src.users import models as um
from src.auth import schemas, utils as auth_utils


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token() -> str:
    return secrets.token_hex(64)


def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = (
        db.query(um.Users)
        .filter(um.Users.email == user_credentials.username)
        .first()
    )
    if not user:
        raise HTTPException(404, "User not registered")

    if not auth_utils.verify(user_credentials.password, user.password):
        raise HTTPException(401, "Incorrect password or email")

    access_token = auth_utils.access_token({"sub": str(user.user_id), "role": user.role})
    refresh_token = create_refresh_token()

    user.refresh_token = hash_token(refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


def refresh(payload: schemas.Token, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)

    user = (
        db.query(um.Users)
        .filter(um.Users.refresh_token == token_hash)
        .first()
    )
    if not user:
        raise HTTPException(403, "Invalid or expired refresh token")

    new_access_token = auth_utils.access_token({"sub": str(user.user_id), "role": user.role})
    new_refresh_token = create_refresh_token()

    user.refresh_token = hash_token(new_refresh_token)
    db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


def logout(payload: schemas.Token, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)

    user = (
        db.query(um.Users)
        .filter(um.Users.refresh_token == token_hash)
        .first()
    )
    if user:
        user.refresh_token = None
        db.commit()

    return {"message": "Logged out successfully"}
