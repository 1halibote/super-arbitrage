import asyncio
import sys
import os
sys.path.insert(0, r"f:\xiangmu\bn-by")
import logging
from backend.execution.exchange_client import ExchangeClient
from backend.execution.key_store import api_key_store

logging.basicConfig(level=logging.INFO)

async def check():
    keys = api_key_store.get_key("bybit")
    if not keys:
        print("No bybit keys")
        return
        
    client = ExchangeClient()
    await client.add_exchange("bybit", keys["api_key"], keys["api_secret"])
    
    cl_spot = client._exchanges["bybit_spot"]
    cl_lin = client._exchanges["bybit_linear"]
    
    f = open('bybit_out.txt', 'w', encoding='utf-8')
    try:
        ords_lin = await cl_lin.fetch_closed_orders("SOL/USDT:USDT", limit=5)
        for o in ords_lin:
            f.write(f"[{o['datetime']}] TYPE:LINEAR {o['side']} {o['status']} qty:{o.get('amount')} filled:{o.get('filled')} price:{o.get('price')} id:{o['id']}\n")
    except Exception as e:
        f.write(f"Linear load failed: {e}\n")

    try:
        ords_spot = await cl_spot.fetch_closed_orders("SOL/USDT", limit=5)
        for o in ords_spot:
            f.write(f"[{o['datetime']}] TYPE:SPOT {o['side']} {o['status']} qty:{o.get('amount')} filled:{o.get('filled')} price:{o.get('price')} id:{o['id']}\n")
    except Exception as e:
        f.write(f"Spot load failed: {e}\n")
        
    f.close()

if __name__ == "__main__":
    asyncio.run(check())
