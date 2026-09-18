from fastapi import WebSocket
from src.middleware.logging import logger as logging_module


logger = logging_module("Websocket")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, dict[int, set[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, business_id: int, user_id: int) -> None:
        await websocket.accept()
        sockets = self.active_connections.setdefault(business_id, {}).setdefault(user_id, set())
        sockets.add(websocket)
        logger.info("ws-connected business_id=%s, user_id=%s", business_id, user_id)

    async def disconnect(self, websocket: WebSocket, business_id: int, user_id: int) -> None:
        sockets = self.active_connections.get(business_id, {}).get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self.active_connections.get(business_id, {}).pop(user_id, None)
        logger.info("ws-disconnected business_id=%s, user_id=%s", business_id, user_id)

    async def broadcast(self, business_id: int, message: str) -> None:
        business_sockets = self.active_connections.get(business_id)
        if not business_sockets:
            return
        for user_id, sockets in list(business_sockets.items()):
            for websocket in list(sockets):
                try:
                    await websocket.send_text(message)
                except Exception:
                    sockets.discard(websocket)
                    if not sockets:
                        business_sockets.pop(user_id, None)
                    logger.error("ws-failed to broadcast message, business=%s", business_id, exc_info=True)

    async def send_personal_message(self, websocket: WebSocket, message: str) -> None:
        await websocket.send_text(message)

    def online_users(self, business_id: int) -> set[int]:
        """User_ids currently connected to a business, excluding dead sockets."""
        business_sockets = self.active_connections.get(business_id)
        if not business_sockets:
            return set()
        alive: set[int] = set()
        for user_id, sockets in list(business_sockets.items()):
            if sockets:
                alive.add(user_id)
        return alive

    def is_connected(self, business_id: int, user_id: int) -> bool:
        return bool(self.active_connections.get(business_id, {}).get(user_id))


manager = ConnectionManager()