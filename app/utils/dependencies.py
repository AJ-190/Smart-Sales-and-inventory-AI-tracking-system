from app.core.config import settings
from app.core.security import verify_token
from fastapi.security import OAuth2PasswordBearer
from fastapi import status, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app import schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    result = (
        db.query(
            models.Users.user_id,
            models.Users.name,
            models.Users.email,
            models.BusinessMember.member_id,
            models.BusinessMember.business_id,
            models.Users.role
        )
        .outerjoin(models.BusinessMember, models.Users.user_id == models.BusinessMember.user_id)
        .filter(models.Users.user_id == user_id)
        .first()
    )

    

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return schemas.UsersOutUsers(
    user_id=result.user_id,
    name=result.name,
    email=result.email,
    member_id=result.member_id,
    business_id=result.business_id,
    role=result.role
)
