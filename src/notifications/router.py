from fastapi import APIRouter, Depends
from src.auth import dependencies as auth_deps
from src.users import models as um
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.database import get_db
from src.notifications import schemas, service
from src.notifications.models import Notification


roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}

router = APIRouter(prefix="/notifications", tags=['Notifications'])

@router.post("/send", status_code=201, response_model=schemas.SendNotification)
async def send_notification(payload: schemas.SendNotification,
                            business_id: int,
                            session: AsyncSession = Depends(get_db),
                            current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    return await service.send_notification(payload, business_id, session, current_user)


@router.get("/get_notifications/{business_id}", response_model=list[schemas.ReadNotification])
async def get_notifications(business_id: int,
                            session: AsyncSession = Depends(get_db),
                            current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    result = await session.execute(select(Notification).where(Notification.business_id == business_id))
    notifications = result.scalars().all()
    return notifications
