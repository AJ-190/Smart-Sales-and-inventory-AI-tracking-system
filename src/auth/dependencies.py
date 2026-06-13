from fastapi.security import OAuth2PasswordBearer
from fastapi import status, HTTPException, Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth import utils as auth_utils
from src.users import models as um
from src.users import schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = auth_utils.verify_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    result = (
        db.query(
            um.Users.user_id,
            um.Users.name,
            um.Users.email,
            um.BusinessMember.member_id,
            um.BusinessMember.business_id,
            um.Users.role
        )
        .outerjoin(um.BusinessMember, um.Users.user_id == um.BusinessMember.user_id)
        .filter(um.Users.user_id == user_id)
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
