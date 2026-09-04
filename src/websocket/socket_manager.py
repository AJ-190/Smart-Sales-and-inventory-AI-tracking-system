from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import defaultdict

router = APIRouter(prefix="/notifications", tags=['Notifications'])
class ConnectionManager:

    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, business_id: int, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[business_id].add(websocket)

    async def disconnect(self, business_id: int, user_id: int, websocket: WebSocket):
        self.active_connections.get(business_id, set()).discard(websocket)
        if business_id in self.active_connections and not self.active_connections[business_id]:
            del self.active_connections[business_id]

    async def broadcast(self, business_id: int, message: str):
        socket_set = self.active_connections.get(business_id)
        if not socket_set:
            return
        dead = []
        for connection in socket_set:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            socket_set.discard(conn)
        if not socket_set:
            self.active_connections.pop(business_id, None)

    async def send_to_user(self, business_id: int, user_id: int, message: str, websocket: WebSocket) -> bool:
        socket_set = self.active_connections.get(business_id)
        if not socket_set:
            self.active_connections[business_id] = set()
            self.active_connections[business_id].add(websocket)
        for connection in socket_set:
            if getattr(connection, "state", None) and connection.state.user_id == user_id:
                await connection.send_text(message)
                return True
        return False


manager = ConnectionManager()

@router.websocket("/ws/{business_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, business_id: int, user_id: int):
    await manager.connect(business_id, user_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_to_user(business_id, user_id, f"You said: {data}", websocket)
    except WebSocketDisconnect:
        await manager.disconnect(business_id, user_id, websocket)