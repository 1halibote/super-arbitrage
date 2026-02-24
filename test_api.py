import sys
import asyncio
import os
sys.path.append('f:\\xiangmu\\bn-by')
from backend.execution.exchange_client import exchange_client
from backend.services.api_key_store import api_key_store

async def test():
    await api_key_store.load()
    await exchange_client.initialize()
    
    print("----- Binance um/account -----")
    bn = await exchange_client.fetch_all_positions_map('binance', is_sf=False)
    for sym, pos_list in bn.items():
        if len(pos_list) > 0:
            for p in pos_list:
                amt = abs(float(p.get('positionAmt', 0)))
                if amt > 0:
                    print(f"BN: {sym} -> AMT: {amt}, ALL: {p}")
                    
    print("\n----- Bybit fetch_positions -----")
    by = await exchange_client.fetch_all_positions_map('bybit', is_sf=False)
    for sym, pos_list in by.items():
        if len(pos_list) > 0:
            for p in pos_list:
                amt = float(p.get('contracts', 0) or p.get('info', {}).get('size', 0) or 0)
                if abs(amt) > 0:
                    print(f"BY: {sym} -> AMT: {amt}, ALL: {p.get('info', p)}")

if __name__ == "__main__":
    asyncio.run(test())
