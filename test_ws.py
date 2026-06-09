import asyncio
import websockets

async def test():
    try:
        async with websockets.connect("ws://localhost:8000/api/v1/notifications/ws/notifications?role_name=USER&access_token=foo") as ws:
            print("Connected!")
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
