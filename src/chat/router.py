import json
from fastapi import APIRouter, HTTPException, Request, status, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db, get_async_session_maker
from src.websocket.socket_manager import manager
from src.chat import models as chm
from src.chat.schemas import WsTicket
from src.db.redis import create_ws_ticket, consume_ws_ticket
from src.auth.dependencies import AccessTokenRequired
from src.users import models as um
from src.config import get_settings

router = APIRouter(prefix="/chat", tags=['Chat'])


class BusinessChat:

    def __init__(self, websocket: WebSocket, business_id: int, user_id: int, session: AsyncSession):
        self.business_id = business_id
        self.user_id = user_id
        self.websocket = websocket
        self.session: AsyncSession = session

    async def group_chat(self):
        await manager.connect(self.websocket, self.business_id, self.user_id)

        try:
            while True:
                raw = await self.websocket.receive_json()
                chat = await self.save_message(raw)

                outgoing_msg = {
                    "from": self.user_id,
                    "business_id": self.business_id,
                    "message": chat.message,
                    "sent_at": chat.created_at.isoformat() if chat.created_at else None
                }

                await manager.broadcast(self.business_id, json.dumps(outgoing_msg))
                await manager.send_personal_message(self.websocket, json.dumps({**outgoing_msg, "self": True}))
        except WebSocketDisconnect:
            await manager.disconnect(self.websocket, self.business_id, self.user_id)

    async def save_message(self, message):
        text = message.get("message") if isinstance(message, dict) else message

        chat = chm.GroupChatMessages(user_id=self.user_id,
                                     business_id=self.business_id,
                                     message=text)

        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat


@router.post("/ws-ticket/{business_id}", response_model=WsTicket)
async def get_ws_ticket(
    business_id: int,
    request: Request,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    try:
        user_id = int(token_data["user"]["sub"])
        role = token_data["user"].get("role")
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data",
        )

    if role != um.RoleEnum.super_admin.value:
        membership = await session.execute(
            select(um.BusinessMember)
            .where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
                um.BusinessMember.is_active.is_(True),
            )
        )
        if membership.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this business",
            )

    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket tickets are unavailable",
        )

    ttl = get_settings().WS_TICKET_TTL
    ticket = await create_ws_ticket(redis, user_id, role, business_id, ttl)
    return WsTicket(ticket=ticket, expires_in=ttl)


@router.websocket("/{business_id}")
async def group_chat_endpoint(websocket: WebSocket, business_id: int):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    redis = getattr(websocket.app.state, "redis", None)
    ticket_data = await consume_ws_ticket(redis, token)
    if not ticket_data:
        await websocket.close(code=4401)
        return

    try:
        if int(ticket_data["business_id"]) != business_id:
            await websocket.close(code=4403)
            return
        user_id = int(ticket_data["user_id"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    role = ticket_data.get("role")

    async with get_async_session_maker() as session:
        if role == um.RoleEnum.super_admin.value:
            pass
        else:
            membership = await session.execute(
                select(um.BusinessMember)
                .where(
                    um.BusinessMember.user_id == user_id,
                    um.BusinessMember.business_id == business_id,
                    um.BusinessMember.is_active.is_(True),
                )
            )
            if membership.scalar_one_or_none() is None:
                await websocket.close(code=4403)
                return

        chat = BusinessChat(websocket, business_id, user_id, session)
        await chat.group_chat()