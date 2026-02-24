import asyncio
import websockets
import json
import sys

async def test():
    ws = await websockets.connect(
        'wss://gateway.test.nado.xyz/v1/subscribe',
        extra_headers={'Sec-WebSocket-Extensions': 'permessage-deflate'}
    )
    # 订阅 BTC-PERP (product_id=2) 的 best_bid_offer
    await ws.send(json.dumps({
        'method': 'subscribe',
        'stream': {'type': 'best_bid_offer', 'product_id': 2},
        'id': 10
    }))
    # 打印订阅确认
    resp = await ws.recv()
    print("SUB RESP:", resp)

    # 等待几条消息
    for i in range(5):
        try:
            msg = await asyncio.wait_for(ws.recv(), 5)
            print(f"MSG {i}: {msg[:300]}")
        except asyncio.TimeoutError:
            print(f"MSG {i}: TIMEOUT")
            break
    await ws.close()

asyncio.run(test())
