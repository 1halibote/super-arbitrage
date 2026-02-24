import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    out = {"binance": [], "bitget": []}
    
    bn_c = ec.get_client('binance_linear')
    if bn_c:
        try:
            pos = await bn_c.fetch_positions()
            if pos: out["binance"].append(pos[0])
        except: pass
            
    bg_c = ec.get_client('bitget_linear')
    if bg_c:
        try:
            pos = await bg_c.fetch_positions()
            if pos: out["bitget"].append(pos[0])
        except: pass
        
    with open('test_fields.json', 'w') as f:
        json.dump(out, f, indent=2)

asyncio.run(test())
