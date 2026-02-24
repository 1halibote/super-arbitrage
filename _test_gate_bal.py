import asyncio
import ccxt.async_support as ccxt
import json
from backend.execution.key_store import api_key_store

async def debug_gate_balance():
    keys = api_key_store.get_key('gate')
    if not keys: 
        print('No Gate key found in local store!')
        return
        
    swap = ccxt.gate({
        'apiKey': keys['api_key'], 
        'secret': keys['api_secret'], 
        'options': {'defaultType': 'swap'}
    })
    
    try:
        print("\n--- Testing Swap Balance ---")
        bf = await swap.fetch_balance()
        # Print the whole structure safely
        print(json.dumps(bf.get('info', {}), indent=2))
        print("\n--- CCXT Parsed ---")
        print("Total:", bf.get('total', {}))
        print("Free:", bf.get('free', {}))
        print("Used:", bf.get('used', {}))
        
    except Exception as e:
        print(f"Error during API call: {e}")
    finally:
        await swap.close()

if __name__ == "__main__":
    asyncio.run(debug_gate_balance())
