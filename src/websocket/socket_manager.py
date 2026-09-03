from fastapi import WebSocket, WebSocketDisconnect
from fastapi import APIRouter


router = APIRouter(tags=['Notifications'])



class ConnectionManager:

    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}

    async def connect(self, business_id: int, websocket: WebSocket):
        await websocket.accept()
        if business_id not in self.active_connections:
            self.active_connections[business_id] = set()
        self.active_connections[business_id].add(websocket)

    async def disconnect(self, business_id: int, websocket: WebSocket):
        if business_id in self.active_connections:
            self.active_connections[business_id].discard(websocket)
            if not self.active_connections[business_id]:
                del self.active_connections[business_id]

    async def broadcast(self, business_id: int, message: str):
        if business_id not in self.active_connections:
            return
        dead = []
        for connection in self.active_connections[business_id]:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.active_connections[business_id].discard(conn)
        if not self.active_connections.get(business_id):
            self.active_connections.pop(business_id, None)


# manager = ConnectionManager()

# @router.websocket("/ws/{business_id}")
# async def websocket_endpoint(websocket: WebSocket, business_id: int):
#     await manager.connect(business_id, websocket)
#     try:
#         while True:
#             data = await websocket.receive_text()
#             await websocket.send_text(f"You wrote: {data}")
#             await manager.broadcast(business_id, f"Client #{business_id} says: {data}")
#     except WebSocketDisconnect:
#         await manager.disconnect(business_id, websocket)
