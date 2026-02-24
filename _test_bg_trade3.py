import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from backend.execution.exchange_client import exchange_client

async def test_options():
    await exchange_client.initialize()
    bg = exchange_client.get_client("bitget_linear")
    if not bg: return

    # 重点：修改 ccxt 默认的 positionMode
    bg.options['positionMode'] = 'one_way'

    sym = "HYPE/USDT:USDT"
    try:
        ticker = await bg.fetch_ticker(sym)
        amt = 6.0 / ticker['last']
        
        # 此时只需传入 side='buy' 或 'sell'，因为 one_way 模式下 CCXT 应该会自动转为 buy_single
        print("--- Open One Way ---")
        res = await bg.create_order(sym, 'market', 'buy', amt, params={'marginCoin': "USDT"})
        print("Success:", res['id'])
        
        print("--- Fetch Positions ---")
        positions = await bg.fetch_positions(params={'marginCoin': 'USDT'})
        for p in positions:
            if p['symbol'] == sym or float(p.get('contracts', 0) or 0) > 0:
                print(f"[{p['symbol']}] contracts={p.get('contracts')} info={p.get('info')}")

        print("--- Close One Way ---")
        await bg.create_order(sym, 'market', 'sell', amt, params={'marginCoin': "USDT", 'reduceOnly': True})
        print("Close Success")
    except Exception as e:
        print("Trade Fail:", repr(e))

    await exchange_client.shutdown()

asyncio.run(test_options())
