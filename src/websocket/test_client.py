import asyncio
import websockets


async def test_websocket():
    async with websockets.connect("ws://localhost:8000/ws/123") as ws:
        await ws.send("Hello, Addy")
        response = await ws.recv()
        print(f"Received: {response}")


if __name__ == "__main__":
    asyncio.run(test_websocket())
