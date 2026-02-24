import asyncio
import json
import websockets

async def test_binance_spot():
    url = "wss://stream.binance.com:443/stream?streams=!ticker@arr"
    # url = "wss://stream.binance.com:9443/stream?streams=!ticker@arr"
    print(f"Connecting to {url}")
    try:
        async with websockets.connect(url) as ws:
            print("Connected! Waiting for messages...")
            for i in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"Received msg keys: {list(data.keys())}")
                if 'data' in data:
                    print(f"Items in data: {len(data['data'])}")
                    if data['data']:
                        print(f"First item: {data['data'][0]['s']} - b:{data['data'][0]['b']} a:{data['data'][0]['a']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_binance_spot())
