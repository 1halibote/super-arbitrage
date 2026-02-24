import asyncio
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store

async def test():
    k = api_key_store.get_key('gate')
    s = ccxt.gate({
        'apiKey': k['api_key'], 'secret': k['api_secret'],
        'options': {'defaultType': 'swap'}
    })
    try:
        await s.load_markets()
        sym = 'DOGE/USDT:USDT'
        m = s.market(sym)
        print(f"Market: {sym}")
        print(f"  contractSize: {m['contractSize']}")
        print(f"  precision.amount: {m['precision']['amount']}")

        # 下1张合约（DOGE contractSize=10, 所以1张=10 DOGE）
        print("\n--- Placing 1 contract sell (short) ---")
        res = await s.create_order(sym, 'market', 'sell', 1)
        print(f"  res['filled'] = {res.get('filled')}")
        print(f"  res['amount'] = {res.get('amount')}")
        print(f"  res['average'] = {res.get('average')}")
        print(f"  res['price'] = {res.get('price')}")
        print(f"  res['cost'] = {res.get('cost')}")
        print(f"  res['info']['size'] = {res.get('info', {}).get('size')}")
        
        # 再平掉
        print("\n--- Closing with reduceOnly ---")
        res2 = await s.create_order(sym, 'market', 'buy', 1, params={'reduceOnly': True})
        print(f"  res2['filled'] = {res2.get('filled')}")
        print(f"  res2['amount'] = {res2.get('amount')}")
        print(f"  res2['cost'] = {res2.get('cost')}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await s.close()

asyncio.run(test())
