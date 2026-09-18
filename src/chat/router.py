import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, status, WebSocket, WebSocketDisconnect, Depends, File, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db, get_async_session_maker
from src.websocket.socket_manager import manager
from src.chat import models as chm
from src.chat import schemas as chs
from src.chat import storage as chat_storage
from src.db.redis import create_ws_ticket, consume_ws_ticket
from src.auth.dependencies import AccessTokenRequired
from src.users import models as um
from src.config import get_settings

router = APIRouter(prefix="/chat", tags=['Chat'])

MAX_MESSAGE_LEN = 5000

# Per-process registry of who is connected to which business chat room so we can
# emit real presence (name + role) without touching the DB on every event.
_chatter_meta: dict[int, dict[int, dict[str, str]]] = {}


def _set_chatter(business_id: int, user_id: int, name: str, role: str):
    _chatter_meta.setdefault(business_id, {})[user_id] = {"name": name, "role": role}


def _remove_chatter(business_id: int, user_id: int):
    _chatter_meta.get(business_id, {}).pop(user_id, None)


def _online_chatters(business_id: int) -> list[dict]:
    room = _chatter_meta.get(business_id, {})
    return [
        {"user_id": uid, **meta}
        for uid, meta in room.items()
        if manager.is_connected(business_id, uid)
    ]


def _parse_user(token_data) -> tuple[int, str]:
    try:
        user_id = int(token_data["user"]["sub"])
        role = token_data["user"].get("role")
        return user_id, role
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data",
        )


async def _is_effective_super_admin(session: AsyncSession, user_id: int) -> bool:
    user = await session.get(um.Users, user_id)
    if not user:
        return False
    return (
        user.role == um.RoleEnum.super_admin
        or (user.email or "") == get_settings().SUPER_ADMIN_EMAIL
    )


async def _ensure_membership(session: AsyncSession, user_id: int, business_id: int) -> None:
    if await _is_effective_super_admin(session, user_id):
        return
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


def _truncate(text: str) -> str:
    return (text or "").strip()[:MAX_MESSAGE_LEN]


def _role_str(role) -> str | None:
    if role is None:
        return None
    return role.value if not isinstance(role, str) else role


async def _fetch_sender(session: AsyncSession, user_id: int, business_id: int) -> dict:
    name = None
    role = None
    if user_id:
        user = await session.get(um.Users, user_id)
        if user:
            name = user.name
            role = _role_str(user.role)
    if role is None and user_id:
        member = await session.execute(
            select(um.BusinessMember.role).where(
                um.BusinessMember.user_id == user_id,
                um.BusinessMember.business_id == business_id,
            )
        )
        role = _role_str(member.scalar_one_or_none())
    return {"name": name, "role": role}


def _ws_payload(msg: chm.GroupChatMessages, sender: dict, self_flag: bool = False) -> dict:
    return {
        "id": msg.id,
        "from": msg.user_id,
        "name": sender.get("name"),
        "role": sender.get("role"),
        "business_id": msg.business_id,
        "message": msg.message,
        "attachment_type": msg.attachment_type,
        "attachment_url": msg.attachment_url,
        "attachment_name": msg.attachment_name,
        "attachment_size": msg.attachment_size,
        "is_edited": msg.is_edited,
        "is_deleted": msg.is_deleted,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "deleted_at": msg.deleted_at.isoformat() if msg.deleted_at else None,
        "sent_at": msg.created_at.isoformat() if msg.created_at else None,
        "self": self_flag,
    }


class BusinessChat:

    def __init__(self, websocket: WebSocket, business_id: int, user_id: int, session: AsyncSession):
        self.business_id = business_id
        self.user_id = user_id
        self.websocket = websocket
        self.session: AsyncSession = session
        self.sender = {"name": None, "role": None}

    async def _send(self, payload: dict):
        await manager.broadcast(self.business_id, json.dumps(payload))

    async def _broadcast_presence(self):
        online = _online_chatters(self.business_id)
        await self._send({"type": "presence", "data": {"business_id": self.business_id, "online": online}})

    async def group_chat(self):
        await manager.connect(self.websocket, self.business_id, self.user_id)
        self.sender = await _fetch_sender(self.session, self.user_id, self.business_id)
        _set_chatter(self.business_id, self.user_id, self.sender.get("name"), self.sender.get("role") or "")

        try:
            await self._broadcast_presence()

            while True:
                try:
                    raw = await self.websocket.receive_json()
                except Exception:
                    break

                if not isinstance(raw, dict):
                    continue

                event_type = raw.get("type")

                if event_type == "typing":
                    await self._send({
                        "type": "typing",
                        "data": {
                            "user_id": self.user_id,
                            "business_id": self.business_id,
                            "name": self.sender.get("name"),
                            "is_typing": bool(raw.get("is_typing")),
                        },
                    })
                    continue

                if event_type == "ping":
                    try:
                        await self.websocket.send_text(json.dumps({"type": "pong", "data": {"t": datetime.now(timezone.utc).isoformat()}}))
                    except Exception:
                        break
                    continue

                message = await self.save_message(raw)
                if message is None:
                    continue

                await self._send({"type": "message", "data": _ws_payload(message, self.sender)})
        except Exception:
            pass
        finally:
            _remove_chatter(self.business_id, self.user_id)
            await manager.disconnect(self.websocket, self.business_id, self.user_id)
            await self._broadcast_presence()

    async def save_message(self, raw: dict) -> chm.GroupChatMessages | None:
        text = _truncate(raw.get("message") or "")
        attachment_url = raw.get("attachment_url") or None
        attachment_type = raw.get("attachment_type") or None
        attachment_name = raw.get("attachment_name") or None
        attachment_size = raw.get("attachment_size")
        try:
            attachment_size = int(attachment_size) if attachment_size else None
        except (TypeError, ValueError):
            attachment_size = None

        if not text and not attachment_url:
            try:
                await self.websocket.send_text(json.dumps({"type": "error", "message": "Message cannot be empty"}))
            except Exception:
                pass
            return None

        chat = chm.GroupChatMessages(
            user_id=self.user_id,
            business_id=self.business_id,
            message=text,
            attachment_url=attachment_url,
            attachment_type=attachment_type,
            attachment_name=attachment_name,
            attachment_size=attachment_size,
        )
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat


@router.post("/ws-ticket/{business_id}", response_model=chs.WsTicket)
async def get_ws_ticket(
    business_id: int,
    request: Request,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket tickets are unavailable",
        )

    ttl = get_settings().WS_TICKET_TTL
    ticket = await create_ws_ticket(redis, user_id, role, business_id, ttl)
    return chs.WsTicket(ticket=ticket, expires_in=ttl)


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

    async with get_async_session_maker() as session:
        if not await _is_effective_super_admin(session, user_id):
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


@router.get("/{business_id}/messages", response_model=chs.ChatHistoryResponse)
async def get_messages(
    business_id: int,
    limit: int = 50,
    before_id: int | None = None,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    limit = max(1, min(limit, 200))

    stmt = select(chm.GroupChatMessages).where(
        chm.GroupChatMessages.business_id == business_id,
        chm.GroupChatMessages.is_deleted.is_(False),
    )
    if before_id is not None:
        stmt = stmt.where(chm.GroupChatMessages.id < before_id)
    stmt = stmt.order_by(chm.GroupChatMessages.id.desc()).limit(limit + 1)

    rows = (await session.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    messages = list(reversed(rows[:limit]))

    total = await session.scalar(
        select(func.count()).select_from(chm.GroupChatMessages).where(
            chm.GroupChatMessages.business_id == business_id,
            chm.GroupChatMessages.is_deleted.is_(False),
        )
    ) or 0

    user_ids = {m.user_id for m in messages if m.user_id}
    senders = {}
    if user_ids:
        user_rows = (await session.execute(
            select(um.Users.user_id, um.Users.name, um.Users.role).where(um.Users.user_id.in_(user_ids))
        )).all()
        member_rows = (await session.execute(
            select(um.BusinessMember.user_id, um.BusinessMember.role).where(
                um.BusinessMember.user_id.in_(user_ids),
                um.BusinessMember.business_id == business_id,
            )
        )).all()

        by_user = {r.user_id: r for r in user_rows}
        member_roles = {r.user_id: _role_str(r[1]) for r in member_rows}
        for uid, ur in by_user.items():
            senders[uid] = {
                "name": ur.name,
                "role": member_roles.get(uid) or _role_str(ur.role),
            }

    items = [_ws_payload(m, senders.get(m.user_id, {}), self_flag=(m.user_id == user_id)) for m in messages]
    next_before_id = messages[0].id if messages and has_more else None

    return chs.ChatHistoryResponse(
        items=[
            chs.ChatMessageOut(
                id=it["id"],
                business_id=it["business_id"],
                user_id=it["from"],
                message=it["message"],
                attachment_type=it["attachment_type"],
                attachment_url=it["attachment_url"],
                attachment_name=it["attachment_name"],
                attachment_size=it["attachment_size"],
                is_edited=it["is_edited"],
                is_deleted=it["is_deleted"],
                edited_at=it["edited_at"],
                deleted_at=it["deleted_at"],
                created_at=it["sent_at"],
                name=it["name"],
                role=it["role"],
                self=it["self"],
            )
            for it in items
        ],
        has_more=has_more,
        next_before_id=next_before_id,
        total=total,
    )


@router.put("/{business_id}/messages/{message_id}", response_model=chs.ChatMessageOut)
async def edit_message(
    business_id: int,
    message_id: int,
    body: chs.MessageEdit,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    msg = await session.get(chm.GroupChatMessages, message_id)
    if not msg or msg.business_id != business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own messages")
    if msg.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deleted messages cannot be edited")

    text = _truncate(body.message)
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty")

    msg.message = text
    msg.is_edited = True
    msg.edited_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(msg)

    sender = await _fetch_sender(session, msg.user_id, business_id)
    await manager.broadcast(business_id, json.dumps({"type": "edit", "data": _ws_payload(msg, sender)}))

    return chs.ChatMessageOut(
        id=msg.id,
        business_id=msg.business_id,
        user_id=msg.user_id,
        message=msg.message,
        attachment_type=msg.attachment_type,
        attachment_url=msg.attachment_url,
        attachment_name=msg.attachment_name,
        attachment_size=msg.attachment_size,
        is_edited=msg.is_edited,
        is_deleted=msg.is_deleted,
        edited_at=msg.edited_at,
        deleted_at=msg.deleted_at,
        created_at=msg.created_at,
        name=sender.get("name"),
        role=sender.get("role"),
        self=msg.user_id == user_id,
    )


@router.delete("/{business_id}/messages/{message_id}", response_model=chs.ChatMessageOut)
async def delete_message(
    business_id: int,
    message_id: int,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    msg = await session.get(chm.GroupChatMessages, message_id)
    if not msg or msg.business_id != business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages")

    msg.is_deleted = True
    msg.deleted_at = datetime.now(timezone.utc)
    msg.message = ""
    await session.commit()
    await session.refresh(msg)

    sender = await _fetch_sender(session, msg.user_id, business_id)
    await manager.broadcast(business_id, json.dumps({"type": "delete", "data": _ws_payload(msg, sender)}))

    return chs.ChatMessageOut(
        id=msg.id,
        business_id=msg.business_id,
        user_id=msg.user_id,
        message=msg.message,
        attachment_type=msg.attachment_type,
        attachment_url=msg.attachment_url,
        attachment_name=msg.attachment_name,
        attachment_size=msg.attachment_size,
        is_edited=msg.is_edited,
        is_deleted=msg.is_deleted,
        edited_at=msg.edited_at,
        deleted_at=msg.deleted_at,
        created_at=msg.created_at,
        name=sender.get("name"),
        role=sender.get("role"),
        self=msg.user_id == user_id,
    )


@router.post("/{business_id}/upload", response_model=chs.AttachmentUploadOut)
async def upload_attachment(
    business_id: int,
    file: UploadFile = File(...),
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)
    return await chat_storage.save_chat_attachment(business_id, file)


@router.get("/{business_id}/unread_count", response_model=chs.UnreadCount)
async def unread_count(
    business_id: int,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    read_pos = await session.get(chm.ChatReadPosition, (user_id, business_id))
    last_read = read_pos.last_read_message_id if read_pos else 0

    stmt = select(func.count()).select_from(chm.GroupChatMessages).where(
        chm.GroupChatMessages.business_id == business_id,
        chm.GroupChatMessages.is_deleted.is_(False),
    )
    if last_read:
        stmt = stmt.where(chm.GroupChatMessages.id > last_read)

    count = await session.scalar(stmt) or 0
    return chs.UnreadCount(unread=count)


@router.put("/{business_id}/read_position", response_model=chs.ReadPositionIn)
async def set_read_position(
    business_id: int,
    body: chs.ReadPositionIn,
    token_data=Depends(AccessTokenRequired),
    session: AsyncSession = Depends(get_db),
):
    user_id, role = _parse_user(token_data)
    await _ensure_membership(session, user_id, business_id)

    read_pos = await session.get(chm.ChatReadPosition, (user_id, business_id))
    latest = await session.scalar(
        select(func.max(chm.GroupChatMessages.id)).where(chm.GroupChatMessages.business_id == business_id)
    ) or 0
    new_last = min(body.last_read_message_id, latest) if body.last_read_message_id else 0

    if read_pos:
        read_pos.last_read_message_id = new_last
        read_pos.updated_at = datetime.now(timezone.utc)
    else:
        read_pos = chm.ChatReadPosition(user_id=user_id, business_id=business_id, last_read_message_id=new_last)
        session.add(read_pos)
    await session.commit()

    return chs.ReadPositionIn(last_read_message_id=new_last)