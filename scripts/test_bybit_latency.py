import asyncio
import websockets
import json
import time
import hmac
import hashlib
import sys
import os

# Add backend to path to use api_key_store
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.execution.key_store import api_key_store

async def test_latency():
    keys = api_key_store.get_key("bybit")
    if not keys:
        print("No Bybit keys found in api_key_store!")
        return

    api_key = keys["api_key"]
    api_secret = keys["api_secret"]
    if not api_key:
        print("Bybit API Key is empty.")
        return

    ws_url = "wss://stream.bybit.com/v5/private"
    
    print(f"Connecting to {ws_url}...")
    
    async with websockets.connect(ws_url) as ws:
        # Auth
        expires = int((time.time() + 10) * 1000)
        sign_str = f"GET/realtime{expires}"
        signature = hmac.new(
            api_secret.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest()

        auth_msg = {
            "op": "auth",
            "args": [api_key, expires, signature]
        }
        await ws.send(json.dumps(auth_msg))
        resp = await ws.recv()
        print(f"Auth Resp: {resp}")

        # Subscribe
        sub_msg = {"op": "subscribe", "args": ["position", "execution"]}
        await ws.send(json.dumps(sub_msg))
        print("Subscribed to position & execution")

        # Ping Loop
        last_ping = 0
        
        while True:
            # Send Ping every 1s
            if time.time() - last_ping > 1.0:
                last_ping = time.time()
                await ws.send(json.dumps({"op": "ping"}))
                # print("Sent PING")

            try:
                # Wait for message with small timeout to allow loop
                msg = await asyncio.wait_for(ws.recv(), timeout=0.1)
                data = json.loads(msg)
                
                op = data.get("op")
                if op == "pong":
                    latency_ms = (time.time() - last_ping) * 1000
                    print(f"PONG: {latency_ms:.1f}ms")
                
                topic = data.get("topic")
                if topic == "position":
                    print(f"[POSITION UPDATE] TS={time.time()}")
                    print(json.dumps(data, indent=2))
                elif topic == "execution":
                    print(f"[EXECUTION UPDATE] TS={time.time()}")
                    print(json.dumps(data, indent=2))
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    try:
        asyncio.run(test_latency())
    except KeyboardInterrupt:
        print("Stopped.")
