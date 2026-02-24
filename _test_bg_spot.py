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
        qty_usdt = 6.0
        # For bitget spot buy, we pass the cost inside params to override it
        print(f"--- Open Spot Buy {sym} Cost: {qty_usdt} ---")
        res = await bg.create_order(sym, 'market', 'buy', 0, params={'cost': qty_usdt})
        print("Success:", res['id'])
        
        # for spot sell, the amount is the base currency (HYPE)
        ticker = await bg.fetch_ticker(sym)
        amt = qty_usdt / ticker['last']
        
        print(f"--- Close Spot Sell {sym} Amt: {amt} ---")
        res2 = await bg.create_order(sym, 'market', 'sell', amt)
        print("Close Success:", res2['id'])
        
    except Exception as e:
        print("Spot Trade Fail:", repr(e))

    await exchange_client.shutdown()

asyncio.run(test_spot())
