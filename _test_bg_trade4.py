import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from backend.execution.exchange_client import exchange_client

async def test_hedge_true():
    await exchange_client.initialize()
    bg = exchange_client.get_client("bitget_linear")
    if not bg: return

    sym = "HYPE/USDT:USDT"
    try:
        ticker = await bg.fetch_ticker(sym)
        amt = 6.0 / ticker['last']
        
        print("--- Open Long ---")
        await bg.create_order(sym, 'market', 'buy', amt, params={'marginCoin': "USDT", 'hedged': True})
        
        print("--- Fetch ---")
        positions = await bg.fetch_positions(params={'marginCoin': 'USDT'})
        for p in positions:
            if p['symbol'] == sym or float(p.get('contracts', 0) or 0) > 0:
                print("== CCXT Keys:")
                for k, v in p.items():
                    if k != 'info': print(f"  {k}: {v}")
                print("== Info Keys:")
                for k, v in p['info'].items():
                    print(f"  {k}: {v}")
        
        print("--- Close Long ---")
        await bg.create_order(sym, 'market', 'sell', amt, params={'marginCoin': "USDT", 'hedged': True, 'reduceOnly': True})
    except Exception as e:
        print("Trade Fail:", repr(e))

    await exchange_client.shutdown()

asyncio.run(test_hedge_true())
