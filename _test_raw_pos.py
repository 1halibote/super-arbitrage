import asyncio
import json
import ccxt.async_support as ccxt
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.execution.key_store import api_key_store

async def test():
    bn_key = api_key_store.get_key('binance')
    if bn_key and bn_key.get('api_key'):
        c = ccxt.binanceusdm({
            'apiKey': bn_key['api_key'],
            'secret': bn_key['api_secret'],
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        try:
            pos = await c.fetch_positions()
            for p in pos:
                amt = float(p.get('contracts') or p.get('positionAmt') or p.get('info', {}).get('positionAmt', 0))
                if amt != 0:
                    out["binance"].append(p)
                    break
        except Exception as e:
            print(f"BN err: {e}")
        finally:
            await c.close()
            
    bg_key = api_key_store.get_key('bitget')
    if bg_key and bg_key.get('api_key'):
        c = ccxt.bitget({
            'apiKey': bg_key['api_key'],
            'secret': bg_key['api_secret'],
            'password': bg_key.get('passphrase', ''),
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        })
        try:
            pos = await c.fetch_positions()
            for p in pos:
                amt = float(p.get('contracts', 0) or p.get('info', {}).get('total', 0) or 0)
                if amt != 0:
                    out["bitget"].append(p)
                    break
        except Exception as e:
            print(f"BG err: {e}")
        finally:
            await c.close()

    with open('test_raw_pos.json', 'w') as f:
        json.dump(out, f, indent=2)

asyncio.run(test())
