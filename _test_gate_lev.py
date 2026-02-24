import asyncio
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store

async def test():
    keys = api_key_store.get_key('gate')
    swap = ccxt.gate({
        'apiKey': keys['api_key'], 'secret': keys['api_secret'],
        'options': {'defaultType': 'swap'}
    })
    try:
        await swap.load_markets()
        sym = 'TRX/USDT:USDT'
        
        # Test 1: set_leverage default
        try:
            res = await swap.set_leverage(3, sym)
            print(f"set_leverage(3, {sym}) OK:", res)
        except Exception as e:
            print(f"set_leverage(3) ERROR: {e}")
            
        # Test 2: set_leverage with settle param
        try:
            res = await swap.set_leverage(3, sym, params={'settle': 'usdt'})
            print(f"set_leverage with settle OK:", res)
        except Exception as e:
            print(f"set_leverage with settle ERROR: {e}")

        # Test 3: check market info for contract size
        m = swap.market(sym)
        print(f"\nMarket info for {sym}:")
        print(f"  contractSize: {m.get('contractSize')}")
        print(f"  precision: {m.get('precision')}")
        print(f"  limits: {m.get('limits')}")
        print(f"  quanto_multiplier from info: {m.get('info', {}).get('quanto_multiplier')}")
            
    finally:
        await swap.close()

asyncio.run(test())
