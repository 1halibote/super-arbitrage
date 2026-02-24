import asyncio
import websockets
import json
import time

async def main():
    try:
        async with websockets.connect("wss://api.gateio.ws/ws/v4/") as ws:
            await ws.send(json.dumps({
                "time": int(time.time()),
                "channel": "spot.book_ticker",
                "event": "subscribe",
                "payload": ["BTC_USDT"]
            }))
            res = await ws.recv()
            print("SPOT SUB:", json.dumps(json.loads(res), indent=2))
            for _ in range(2):
                update = await ws.recv()
                print("SPOT UPDATE:", json.dumps(json.loads(update), indent=2))
    except Exception as e:
        print("SPOT ERR:", e)

    print("="*50)

    try:
        async with websockets.connect("wss://fx-ws.gateio.ws/v4/ws/usdt") as ws:
            await ws.send(json.dumps({
                "time": int(time.time()),
                "channel": "futures.book_ticker",
                "event": "subscribe",
                "payload": ["BTC_USDT"]
            }))
            res = await ws.recv()
            print("FUT SUB:", json.dumps(json.loads(res), indent=2))
            for _ in range(2):
                update = await ws.recv()
                print("FUT UPDATE:", json.dumps(json.loads(update), indent=2))
    except Exception as e:
        print("FUT ERR:", e)

if __name__ == "__main__":
    asyncio.run(main())
