import asyncio
import websockets
import json
import time

async def test_gate_spot():
    async with websockets.connect("wss://api.gateio.ws/ws/v4/") as ws:
        sub = {
            "time": int(time.time()),
            "channel": "spot.book_ticker",
            "event": "subscribe",
            "payload": ["BTC_USDT"]
        }
        await ws.send(json.dumps(sub))
        res = await ws.recv()
        print("SPOT SUB:", res)
        # Wait for an update
        for _ in range(3):
            update = await ws.recv()
            print("SPOT UPDATE:", update)
            if json.loads(update).get("event") == "update":
                break

async def test_gate_future():
    async with websockets.connect("wss://fx-ws.gateio.ws/v4/ws/usdt") as ws:
        sub = {
            "time": int(time.time()),
            "channel": "futures.book_ticker",
            "event": "subscribe",
            "payload": ["BTC_USDT"]
        }
        await ws.send(json.dumps(sub))
        res = await ws.recv()
        print("FUTURE SUB:", res)
        # Wait for an update
        for _ in range(3):
            update = await ws.recv()
            print("FUTURE UPDATE:", update)
            if json.loads(update).get("event") == "update":
                break

async def main():
    await test_gate_spot()
    print("-" * 40)
    await test_gate_future()

if __name__ == "__main__":
    asyncio.run(main())
