import asyncio
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store

async def test():
    keys = api_key_store.get_key('gate')
    swap = ccxt.gate({'apiKey': keys['api_key'], 'secret': keys['api_secret'], 'options': {'defaultType': 'swap'}})
    try:
        await swap.load_markets()
        for sym in ['AZTEC/USDT:USDT', 'BTC/USDT:USDT']:
            m = swap.market(sym)
            cs = m.get('contractSize')
            qm = m.get('info', {}).get('quanto_multiplier')
            print(f"{sym}: contractSize={cs}, quanto_multiplier={qm}")
    finally:
        await swap.close()

asyncio.run(test())
