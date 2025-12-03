import asyncio
import websockets
import json

async def listen():
    uri = "ws://172.20.10.4:8000/ws"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)
            print("RSSI:", data["rssi"], "detected:", data["detected"])

asyncio.run(listen())