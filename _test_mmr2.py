import asyncio
import json
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store

async def run():
    # Bybit
    bb_keys = api_key_store.get_key("bybit")
    if bb_keys:
        bb = ccxt.bybit({'apiKey': bb_keys['api_key'], 'secret': bb_keys['api_secret']})
        try:
            pos = await bb.fetch_positions(params={'category': 'linear', 'limit': 10})
            if pos: print("--- Bybit ---\n", json.dumps(pos[0]['info'], indent=2))
        except Exception as e: print("Bybit err:", e)
        await bb.close()
        
    # Bitget
    bg_keys = api_key_store.get_key("bitget")
    if bg_keys:
        bg = ccxt.bitget({'apiKey': bg_keys['api_key'], 'secret': bg_keys['api_secret'], 'password': bg_keys.get('passphrase')})
        try:
            pos = await bg.fetch_positions(params={'productType': 'USDT-FMC'})
            if pos: 
                print("--- Bitget Standard ---")
                print(json.dumps({k: v for k, v in pos[0].items() if k != 'info'}, indent=2))
                print("--- Bitget Raw ---")
                print(json.dumps(pos[0]['info'], indent=2))
        except Exception as e: print("Bitget err:", e)
        await bg.close()
        
    # Gate
    gt_keys = api_key_store.get_key("gate")
    if gt_keys:
        gt = ccxt.gate({'apiKey': gt_keys['api_key'], 'secret': gt_keys['api_secret']})
        try:
            pos = await gt.fetch_positions()
            if pos:
                print("--- Gate Standard ---")
                print(json.dumps({k: v for k, v in pos[0].items() if k != 'info'}, indent=2))
                print("--- Gate Raw ---")
                print(json.dumps(pos[0]['info'], indent=2))
        except Exception as e: print("Gate err:", e)
        await gt.close()

asyncio.run(run())
