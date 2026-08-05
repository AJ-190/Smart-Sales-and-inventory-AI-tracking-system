from fastapi import APIRouter, Depends
from src.database import get_db
from src.debts import service as debt_service
from src.auth import dependencies as auth_deps
from src.debts import schemas
from src.users import models as um
from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/debts", tags=["Debts"])

roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}

@router.post("/add_debt/{business_id}/{customer_id}", response_model=schemas.DebtResponse)
async def add_debt(post: schemas.AddDebt,
                   business_id: int,
                   customer_id: int,
                   session: AsyncSession = Depends(get_db),
                   current_user: um.Users = Depends(auth_deps.role_checker([*roles]))
                   ):
    return await debt_service.add_debt(post, business_id, customer_id, session, current_user)

@router.get("/{business_id}")
async def get_debts(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles]))
):
    return await debt_service.get_debts(business_id, db, current_user)

@router.get("/customers/{business_id}", response_model=list[schemas.CustomerDebt])
async def get_customers_with_debt(
    business_id: int, 
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    limit:int = 100,
    skip: int = 0,
    amount_gre: float | None = None,
    amount_les: float | None =  None,
    search: str | None = None):
    
    return await debt_service.get_customers_with_debt(business_id, db, current_user, limit, skip, search, amount_gre, amount_les) 


@router.get("/customers/{business_id}/{customer_id}", response_model=schemas.CustomerDebt)
async def get_customer_with_debt(business_id: int,
                                 customer_id: int, 
                                 session: AsyncSession = Depends(get_db),
                                 current_user=Depends(auth_deps.role_checker([*roles])),
                                 ):
                                 
    return await debt_service.get_customer_with_debt(business_id, customer_id, session, current_user)

@router.put("/update_customer_debt/{business_id}/{customer_id}", response_model=schemas.CustomerDebt)
async def update_customer_debt(post: schemas.UpdateDebt,
                     business_id: int, 
                     customer_id: int,
                     current_user: um.Users = Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin])),
                     session:AsyncSession = Depends(get_db)):
    return await debt_service.update_customer_with_debt(post, business_id, customer_id, session, current_user)


@router.get("/customer_transactions/{business_id}/{customer_id}", response_model=list[schemas.CustomerTransactions])
async def get_customer_transactions(business_id: int,
                                    customer_id:int,
                                    current_user: um.Users = Depends(auth_deps.role_checker([*roles])),
                                    session: AsyncSession = Depends(get_db)):
    return await debt_service.get_transactions(business_id, customer_id, current_user, session)
    
    
@router.post("/reminders/{business_id}", response_model=schemas.ReminderResponse)
async def schedule_reminders(business_id: int, 
                             post: schemas.scheduleReminder,
                             current_user: um.Users = Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin])),
                             session: AsyncSession = Depends(get_db)):
    return await debt_service.set_reminders(business_id,current_user, session, post)

@router.get("/reminders/{business_id}", response_model=list[schemas.ReminderResponse])
async def get_reminders(business_id: int,
                        post: schemas.GetReminders,
                        current_user: um.Users = Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin])),
                        session: AsyncSession = Depends(get_db)):
    return await debt_service.get_reminders(business_id, current_user, session, post)

@router.put("/reminders/{business_id}/{reminder_id}", response_model=schemas.ReminderResponse)
async def update_reminder(business_id: int,
                          reminder_id: int,
                          post: schemas.UpdateReminder,
                          current_user: um.Users = Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin])),
                          session: AsyncSession = Depends(get_db)):
    return await debt_service.edit_reminder(business_id, reminder_id, current_user, session, post)

@router.delete("/reminders/{business_id}/{reminder_id}")
async def delete_reminder(business_id: int,
                          reminder_id: int,
                          current_user: um.Users = Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin])),
                          session: AsyncSession = Depends(get_db)):
    return await debt_service.delete_reminder(business_id, reminder_id, current_user, session)