import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    bn_c = ec.get_client('binance_papi')
    if bn_c:
        try:
            acc = await bn_c.request('account', api='papi')
            print(f"uniMMR: {acc.get('uniMMR')}")
            print(f"accountMaintMargin: {acc.get('accountMaintMargin')}")
            print(f"accountEquity: {acc.get('accountEquity')}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test())
