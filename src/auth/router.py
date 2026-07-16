from fastapi import APIRouter, Body, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from src.database import get_db
from src.auth import schemas, service as auth_service
from src.celery_tasks.otp_task import send_otp, verify_otp
from src.users.schemas import UserSignUpResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.users import service


router = APIRouter(prefix="/auth", tags=["Authentication"])


class EmailRequest(BaseModel):
    email: EmailStr


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

@router.post("/otp/get_code")
async def get_verification_code(body: EmailRequest):
    return await send_otp(body.email)
    
@router.post("/otp/verification", response_model=UserSignUpResponse)
async def verify_otp_code(post: schemas.Otp_verification,  db: AsyncSession = Depends(get_db)):
    verify = await verify_otp(post.email, post.otp)
    if not verify:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 
                            detail="Incorrect OTP-verification code")
    user = await auth_service.get_user_by_email(post.email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not registered")
    
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return user
    
@router.post("/logout")
async def logout(
    payload: schemas.Token,
    db = Depends(get_db)
):
    return await auth_service.logout(payload, db)
