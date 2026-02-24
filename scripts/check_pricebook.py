import asyncio, aiohttp, json

async def main():
    async with aiohttp.ClientSession() as s:
        r = await s.get("http://localhost:8000/api/data")
        d = await r.json()
        snapshot = d.get("prices", {})
        sol_keys = [k for k in snapshot.keys() if "SOL" in k.upper()]
        print("SOL-related keys:", sol_keys)
        for k in sol_keys:
            exs = list(snapshot[k].keys())
            print(f"  {k}: {exs}")

asyncio.run(main())
