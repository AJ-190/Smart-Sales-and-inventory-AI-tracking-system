from fastapi import APIRouter, Body, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from src.database import get_db
from src.auth import schemas, service as auth_service
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
async def get_verification_code(current_user = Depends(role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier, um.RoleEnum.viewer, um.RoleEnum.user]))):
    return await send_otp(current_user.email)

@router.post("/verify_user/{user_id}", response_model=us_schema.UserSignUpResponse)
async def veirfy_user(user_id: int, session: AsyncSession = Depends(get_db), current_user:um.Users = Depends(role_checker([um.RoleEnum.super_admin]))):
    user = (await session.execute(select(um.Users).where(um.Users.user_id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_verified = True
    await session.commit()
    await session.refresh(user)
    return user
    
@router.post("/otp/verification", response_model=UserSignUpResponse)
async def verify_otp_code(otp: schemas.Otp_veriification_code, 
                          db: AsyncSession = Depends(get_db),
                          current_user = Depends(role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier, um.RoleEnum.viewer, um.RoleEnum.user]))):
    verify = await verify_otp(current_user.email, otp.otp)
    if not verify:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 
                            detail="Incorrect OTP-verification code")
    user = await auth_service.get_user_by_email(current_user.email, db)
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
