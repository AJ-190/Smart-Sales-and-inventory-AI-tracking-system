from fastapi import APIRouter, Body, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from src.database import get_db
from src.auth import schemas, service as auth_service, utils
from src.celery_tasks.otp_task import send_otp, verify_otp
from src.users.schemas import UserSignUpResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.users import service, models as um, schemas as us_schema
from src.auth.dependencies import role_checker
from sqlalchemy import select

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
async def get_verification_code(email: schemas.Email):
    return await send_otp(email.email, forgot_pass=False)

@router.post("/verify_user", response_model=us_schema.UserSignUpResponse)
async def veirfy_user(email: schemas.Email, session: AsyncSession = Depends(get_db)):
    user = (
        await session.execute(
            select(um.Users).where(um.Users.email == email.email)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_verified = True
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/forgot_password")
async def forgot_password(useremail: schemas.Email, session: AsyncSession = Depends(get_db)):
    if not await auth_service.get_user_by_email(useremail.email, session):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                            detail="User not registered")
        
    return await send_otp(useremail.email, forgot_pass=True)


@router.post("/verify/forgot_password", response_model=us_schema.UserSignUpResponse)
async def verify_forgot_password(otp: schemas.Otp_veriification_code,
                                 
                                 session: AsyncSession = Depends(get_db)):
    if otp.password is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No password entered")
    
    user = await auth_service.get_user_by_email(otp.email, session)
    if not await verify_otp(otp.email,otp=otp.otp, forgot_pass=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect OTP-verification code")
    
    
    user.password = utils.hash(otp.password)
    return user
    
@router.post("/otp/verification", response_model=UserSignUpResponse)
async def verify_otp_code(otp: schemas.Otp_veriification_code, 
                          db: AsyncSession = Depends(get_db),):
    verify = await verify_otp(otp.email, otp.otp, forgot_pass=True)
    if not verify:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 
                            detail="Incorrect OTP-verification code")
    user = await auth_service.get_user_by_email(otp.email, db)
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
