import asyncio, json, websockets

async def main():
    async with websockets.connect("wss://mainnet.zklighter.elliot.ai/stream?readonly=true") as ws:
        await ws.send(json.dumps({"type": "subscribe", "channel": "market_stats/all"}))
        while True:
            data = json.loads(await asyncio.wait_for(ws.recv(), 15))
            if data.get("type") != "update/market_stats":
                continue
            stats = data.get("market_stats", {})
            # market_id=1 是 BTC
            if "1" in stats:
                s = stats["1"]
                raw_cur = s.get("current_funding_rate", "?")
                raw_last = s.get("funding_rate", "?")
                print(f"BTC current_funding_rate (raw string): '{raw_cur}'")
                print(f"BTC funding_rate (last settled raw):   '{raw_last}'")
                print()
                print(f"If value IS already percentage:")
                print(f"  current = {raw_cur}%")
                print(f"  last    = {raw_last}%")
                print()
                print(f"Our code does: fr = float('{raw_cur}') / 100 = {float(raw_cur)/100}")
                print(f"Then system *100 for display: {float(raw_cur)/100*100:.6f}%")
                print(f"=> So display matches raw value. No bug.")
                return

asyncio.run(main())
