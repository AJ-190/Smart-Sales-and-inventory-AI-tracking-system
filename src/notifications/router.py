from fastapi import WebSocket, APIRouter, Depends, WebSocketDisconnect
from src.websocket import dependencies, socket_manager
from src.users import models as um
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from src.notifications import schemas
from src.notifications.models import Notification



router = APIRouter(prefix="/notifications", tags=['Notifications'])
manager = socket_manager.ConnectionManager()

@router.websocket("/ws/notifications/{business_id}")
async def send_notification(business_id: int,
                        current_user: um.Users = Depends(dependencies.get_current_user_ws),
                        session: AsyncSession = Depends(get_db)):
    
    await manager.connect(business_id, WebSocket)
    try:
        
        while True:
            text = await WebSocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(business_id, WebSocket)
        
    notification = Notification(user_id = current_user.user_id,
                                business_id = business_id,
                                message=text)
    
    session.add(notification)
    await session.commit()
    