import asyncio, sys, json, logging, websockets
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO)

async def main():
    url = "wss://gateway.prod.nado.xyz/v1/subscribe"
    async with websockets.connect(url) as ws:
        # 订阅所有 perp 产品的 funding_rate
        for pid in [2, 4, 6, 8, 10]:
            await ws.send(json.dumps({
                "method": "subscribe",
                "stream": {"type": "funding_rate", "product_id": pid},
                "id": pid,
            }))

        count = 0
        while count < 20:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(msg)
                if data.get("type") == "funding_rate":
                    pid = data.get("product_id")
                    fr_raw = data.get("funding_rate_x18", "0")
                    fr_val = float(fr_raw) / 1e18
                    fr_pct = fr_val * 100
                    print(f"product_id={pid}: funding_rate_x18={fr_raw}")
                    print(f"  -> raw={fr_val:.10f}, pct={fr_pct:.6f}%")
                    print(f"  -> all fields: {json.dumps(data)}")
                    count += 1
            except asyncio.TimeoutError:
                print("Timeout waiting for funding_rate, breaking")
                break

asyncio.run(main())
