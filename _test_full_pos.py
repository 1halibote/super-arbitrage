import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    # Gate
    gc = ec.get_client('gate_linear')
    if gc:
        print("--- Gate ---")
        pos = await gc.fetch_positions()
        for p in pos:
            amt = p.get('contracts') or p.get('positionAmt')
            if float(amt or 0) != 0:
                print(json.dumps(p, indent=2))
                
    # Bitget
    bc = ec.get_client('bitget_linear')
    if bc:
        print("\n--- Bitget ---")
        pos = await bc.fetch_positions()
        for p in pos:
            amt = p.get('contracts') or float(p.get('info', {}).get('total', 0))
            if float(amt or 0) != 0:
                print(json.dumps(p, indent=2))

asyncio.run(test())
