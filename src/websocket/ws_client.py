import asyncio
import websockets


TOKEN = "YOUR_JWT_TOKEN_HERE"
BUSINESS_ID = 123
USER_ID = 1


async def test_websocket():
    uri = f"ws://localhost:8000/notifications/ws/{BUSINESS_ID}/{USER_ID}"
    async with websockets.connect(uri) as ws:
        await ws.send("Hello, Addy")
        response = await ws.recv()
        print(f"Received: {response}")


if __name__ == "__main__":
    asyncio.run(test_websocket())
