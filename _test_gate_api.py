import asyncio
import ccxt.async_support as ccxt
import json
from backend.execution.key_store import api_key_store

async def test():
    keys = api_key_store.get_key('gate')
    if not keys: 
        print('No Gate key found in local store!')
        return
        
    print('✅ Key extracted successfully')
    spot = ccxt.gate({
        'apiKey': keys['api_key'], 
        'secret': keys['api_secret'], 
        'options': {'defaultType': 'spot'}
    })
    swap = ccxt.gate({
        'apiKey': keys['api_key'], 
        'secret': keys['api_secret'], 
        'options': {'defaultType': 'swap'}
    })
    
    try:
        print("\n--- Testing Spot ---")
        bs = await spot.fetch_balance()
        print('Spot USDT Balance:', bs.get('total', {}).get('USDT', 0))
        
        print("\n--- Testing Swap (Linear) ---")
        bf = await swap.fetch_balance()
        print('Swap USDT Balance:', bf.get('total', {}).get('USDT', 0))
        
        pos = await swap.fetch_positions()
        print(f'Total Open Positions: {len(pos)}')
        if pos:
            print("First position RAW info keys:", list(pos[0].get('info', {}).keys()))
            print("First position size/side:", pos[0].get('contracts'), pos[0].get('side'))
            
    except Exception as e:
        print(f"Error during API call: {e}")
    finally:
        await spot.close()
        await swap.close()

if __name__ == "__main__":
    asyncio.run(test())
