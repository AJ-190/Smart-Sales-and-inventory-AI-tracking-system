from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sales_tracker.app import schemas, models, database
from sqlalchemy.orm import Session
from sales_tracker.app.core import security
from sales_tracker.app.utils import dependencies



router = APIRouter(prefix="/auth", tags=['Authentication'])


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    
    user = db.query(models.Users).filter(models.Users.email == user_credentials.username).first()
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Account not registered"
        )

    if not security.verify(user_credentials.password, user.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password or email"
        )

    # Keep token lean
    token = security.access_token({
        "sub": str(user.user_id),
        "role": user.role
    })

    return {"access_token": token, "token_type": "Bearer"}