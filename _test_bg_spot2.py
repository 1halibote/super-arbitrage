import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from backend.execution.exchange_client import exchange_client

async def test_spot():
    await exchange_client.initialize()
    bg = exchange_client.get_client("bitget_spot")
    if not bg: return

    sym = "HYPE/USDT"
    
    try:
        qty_usdt = 5.0
        print(f"--- Open Spot Buy {sym} Cost: {qty_usdt} ---")
        res = await bg.create_order(sym, 'market', 'buy', 0, params={'cost': qty_usdt})
        print("Buy Success keys:")
        for k, v in res.items():
            if v is not None and k != 'info':
                print(f"  {k}: {v}")
        
    except Exception as e:
        print("Spot Trade Fail:", repr(e))

    await exchange_client.shutdown()

asyncio.run(test_spot())
