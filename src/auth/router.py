from fastapi import APIRouter, Body, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from src.db.database import get_db
from src.auth import schemas, service as auth_service, utils
from src.celery_tasks.otp_task import send_otp, verify_otp
from src.users.schemas import UserSignUpResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from src.users import service, models as um, schemas as us_schema
from src.auth import dependencies as auth_deps
from sqlalchemy import select
from src.auth.utils import verify

router = APIRouter(prefix="/auth", tags=["Authentication"])


class EmailRequest(BaseModel):
    email: EmailStr

allowed_roles = {um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.viewer, um.RoleEnum.user}

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
async def verify_user(email: schemas.Email, current_user=Depends(auth_deps.get_current_user), session: AsyncSession = Depends(get_db)):
    if current_user.role != um.RoleEnum.super_admin and current_user.email != email.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to verify this account")
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
async def verify_forgot_password(otp: schemas.OtpVerificationCode,
                                 
                                 session: AsyncSession = Depends(get_db)):
    if otp.password is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No password entered")
    
    user = await auth_service.get_user_by_email(otp.email, session)
    if not await verify_otp(otp.email,otp=otp.otp, forgot_pass=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect OTP-verification code")
    
    
    user.password = utils.hash(otp.password.get_secret_value())
    await session.commit()
    await session.refresh(user)
    return user

@router.post("/verify/change_password", status_code=200)
async def change_password(passwords: schemas.Passwords, current_user = Depends(auth_deps.role_checker([*allowed_roles])), session: AsyncSession = Depends(get_db)):
    return await auth_service.change_password(current_user, session, passwords)

@router.post("/verify/password", status_code=200)
async def verify_password(payload: schemas.PasswordVerify, current_user: um.Users = Depends(auth_deps.role_checker([*allowed_roles])), session: AsyncSession = Depends(get_db)):
    user = (await session.execute(select(um.Users).where(um.Users.user_id == current_user.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not verify(payload.password.get_secret_value(), user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="incorrect password")
    return 

@router.post("/otp/verify_change_password", status_code=200)
async def verify_change_password_otp(payload: schemas.OtpCode, current_user = Depends(auth_deps.role_checker(allowed_roles))):
    return await auth_service.verify_change_password_otp(current_user, payload.otp)
    
@router.post("/otp/verification", response_model=UserSignUpResponse)
async def verify_otp_code(otp: schemas.OtpVerificationCode, 
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
