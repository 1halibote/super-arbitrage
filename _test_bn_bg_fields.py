import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    print("\n--- Binance Linear ---")
    bn_c = ec.get_client('binance_linear')
    if bn_c:
        try:
            pos = await bn_c.fetch_positions()
            for p in pos:
                amt = p.get('contracts') or p.get('positionAmt') or float(p.get('info', {}).get('positionAmt', 0))
                if float(amt or 0) != 0:
                    print(json.dumps(p, indent=2))
                    break # just need one
        except Exception as e:
            print(f"BN error: {e}")
            
    print("\n--- Bitget Linear ---")
    bg_c = ec.get_client('bitget_linear')
    if bg_c:
        try:
            pos = await bg_c.fetch_positions()
            for p in pos:
                amt = float(p.get('info', {}).get('total', 0) or p.get('contracts', 0) or 0)
                if amt != 0:
                    print(json.dumps(p, indent=2))
                    break
        except Exception as e:
            print(f"BG error: {e}")

asyncio.run(test())
