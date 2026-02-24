import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        msg = await asyncio.wait_for(ws.recv(), 5)
        data = json.loads(msg)

        # 获取 prices
        prices = data.get("prices", [])
        btc = [p for p in prices if p.get("symbol") == "BTCUSDT"]
        if btc:
            b = btc[0]
            print("=== BTCUSDT from /ws ===")
            for ex in ["binance_spot","binance_future","bybit_spot","bybit_future",
                        "bitget_spot","bitget_future","gate_spot","gate_future",
                        "nado_spot","nado_future","lighter_spot","lighter_future"]:
                val = b.get(ex, {})
                if val and val.get("bid", 0) > 0:
                    print(f"  {ex:20s}: bid={val['bid']:>10.2f}  ask={val['ask']:>10.2f}")

        # 获取 sf
        sf = data.get("sf", {})
        btc_sf = sf.get("BTCUSDT", {})
        if btc_sf:
            print("\n=== BTCUSDT SF pairs ===")
            for pair, item in list(btc_sf.items())[:5]:
                print(f"  {pair:30s}: open={item.get('openSpread','?')}%")

asyncio.run(main())
