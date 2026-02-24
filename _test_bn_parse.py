import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    pos_map = await ec.fetch_all_positions_map('binance_linear', is_sf=False)
    print(f"BN Map keys: {list(pos_map.keys())[:10]}")
    
    # find sym that has positions
    for sym, pos_list in pos_map.items():
        if not pos_list: continue
        
        # calculate
        qty, val, ep, pnl, liq, adl, mmr = ec.parse_position_list(pos_list, sym, target_side='long')
        if qty > 0:
            print(f"LONG {sym}: qty={qty} val={val} liq={liq} adl={adl} mmr={mmr}")
            print(json.dumps(pos_list, indent=2))
            break
            
        qty, val, ep, pnl, liq, adl, mmr = ec.parse_position_list(pos_list, sym, target_side='short')
        if qty > 0:
            print(f"SHORT {sym}: qty={qty} val={val} liq={liq} adl={adl} mmr={mmr}")
            print(json.dumps(pos_list, indent=2))
            break

asyncio.run(test())
