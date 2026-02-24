import sys
import os
sys.path.append(os.path.dirname(__file__))

import asyncio
from backend.execution.exchange_client import ExchangeClient

async def main():
    client = ExchangeClient()
    await client.initialize()
    
    b_spot = client._exchanges.get('binance_spot')
    if b_spot:
        try:
            print("Fetching bn balance...")
            bal = await b_spot.fetch_balance()
            total = bal.get('total', {})
            print('bn_spot total:', {k:v for k,v in total.items() if v > 0})
        except Exception as e:
            print('Spot error:', e)
    else:
        print('no bn_spot')

if __name__ == '__main__':
    asyncio.run(main())
