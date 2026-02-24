import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    print("\n--- Binance Linear ---")
    bn_c = ec.get_client('binance_linear')
    if bn_c:
        try:
            pos = await bn_c.fetch_positions()
            for p in pos[:3]: # print first 3
                print(json.dumps(p, indent=2))
        except Exception as e:
            print(f"BN error: {e}")
            
    print("\n--- Bitget Linear ---")
    bg_c = ec.get_client('bitget_linear')
    if bg_c:
        try:
            pos = await bg_c.fetch_positions()
            for p in pos[:3]: # print first 3
                print(json.dumps(p, indent=2))
        except Exception as e:
            print(f"BG error: {e}")

asyncio.run(test())
