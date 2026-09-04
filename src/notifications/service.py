from sqlalchemy.ext.asyncio import AsyncSession
from src.notifications import schemas
from src.notifications.models import Notification
from src.websocket.socket_manager import manager
from src.users import models as um


async def send_notification(payload: schemas.SendNotification, business_id: int, session: AsyncSession, current_user: um.Users) -> dict:
    notification = Notification(
        user_id=payload.user_id,
        business_id=payload.business_id,
        title=payload.title,
        message=payload.message,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)

    await manager.broadcast(payload.business_id, payload.message)
    await manager.broadcast(business_id, f"New notification: {notification.message}")
    return {
        "notification_id": notification.notification_id,
        "user_id": notification.user_id,
        "business_id": notification.business_id,
        "message": notification.message,
    }
