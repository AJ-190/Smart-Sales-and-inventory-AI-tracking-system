from fastapi import APIRouter, Depends, HTTPException
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
                            unread_only: bool = False,
                            session: AsyncSession = Depends(get_db),
                            current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    query = select(Notification).where(
        Notification.business_id == business_id,
        Notification.user_id == current_user.user_id,
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc(), Notification.notification_id.desc())
    result = await session.execute(query)
    return result.scalars().all()


async def _owned_or_404(session: AsyncSession, notification_id: int, current_user: um.Users):
    """Load a notification, but only if it belongs to the caller."""
    result = await session.execute(
        select(Notification).where(Notification.notification_id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    is_privileged = current_user.role in (um.RoleEnum.admin, um.RoleEnum.super_admin)
    if notification.user_id != current_user.user_id and not is_privileged:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.patch("/{notification_id}/read", response_model=schemas.ReadNotification)
async def mark_notification_read(notification_id: int,
                                 session: AsyncSession = Depends(get_db),
                                 current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    notification = await _owned_or_404(session, notification_id, current_user)
    if not notification.is_read:
        notification.is_read = True
        await session.commit()
        await session.refresh(notification)
    return notification


@router.post("/read-all/{business_id}", response_model=schemas.MarkReadResult)
async def mark_all_read(business_id: int,
                        session: AsyncSession = Depends(get_db),
                        current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    """Mark every unread notification for this user in the business as read."""
    result = await session.execute(
        select(Notification).where(
            Notification.business_id == business_id,
            Notification.user_id == current_user.user_id,
            Notification.is_read.is_(False),
        )
    )
    notifications = result.scalars().all()
    for notification in notifications:
        notification.is_read = True
    if notifications:
        await session.commit()
    return {"updated_count": len(notifications)}


@router.delete("/{notification_id}", response_model=schemas.NotificationDeleteResult)
async def delete_notification(notification_id: int,
                              session: AsyncSession = Depends(get_db),
                              current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    notification = await _owned_or_404(session, notification_id, current_user)
    await session.delete(notification)
    await session.commit()
    return {"deleted_id": notification_id, "deleted_count": 1}


@router.delete("/read/{business_id}", response_model=schemas.NotificationDeleteResult)
async def clear_read_notifications(business_id: int,
                                   session: AsyncSession = Depends(get_db),
                                   current_user: um.Users = Depends(auth_deps.role_checker([*roles]))):
    """Bulk-clear the caller's already-read notifications, keeping unread ones."""
    result = await session.execute(
        select(Notification).where(
            Notification.business_id == business_id,
            Notification.user_id == current_user.user_id,
            Notification.is_read.is_(True),
        )
    )
    notifications = result.scalars().all()
    for notification in notifications:
        await session.delete(notification)
    if notifications:
        await session.commit()
    return {"deleted_id": 0, "deleted_count": len(notifications)}
