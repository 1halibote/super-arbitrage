import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from backend.execution.exchange_client import exchange_client

async def test_bitget_mode():
    await exchange_client.initialize()
    bg_linear = exchange_client.get_client("bitget_linear")
    
    if not bg_linear:
        print("Wait")
        return

    sym = "HYPE/USDT:USDT"
    
    ticker = await bg_linear.fetch_ticker(sym)
    price = ticker['last']
    amt = 6.0 / price
    print(f"\n----- Opening order amt: {amt} -----")
    
    market = bg_linear.market(sym)
    
    req = {
        'symbol': market['id'],
        'marginCoin': 'USDT',
        'orderType': 'market',
        'side': 'buy_single',  # TRYING SINGLE
        'size': bg_linear.amount_to_precision(sym, amt)
    }
    print("Payload v1 buy_single:", req)
    try:
        # mix/v1/order/placeOrder
        res = await bg_linear.request('mix/v1/order/placeOrder', 'private', 'POST', req)
        print("Raw Order opened:", res)
    except Exception as e:
        print("buy_single fail:", repr(e))


    req['side'] = 'buy'
    print("\nPayload v1 buy:", req)
    try:
        res = await bg_linear.request('mix/v1/order/placeOrder', 'private', 'POST', req)
        print("Raw Order opened:", res)
    except Exception as e:
        print("buy fail:", repr(e))

    await exchange_client.shutdown()

asyncio.run(test_bitget_mode())
