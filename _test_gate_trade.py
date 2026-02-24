import asyncio
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store

async def test_gate_trade():
    keys = api_key_store.get_key('gate')
    if not keys: return
        
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
        print("\n--- Testing Spot Market Buy (cost based vs amount based) ---")
        try:
            # Test market buy with amount=2 (in ccxt gate market buy, is amount the base coin or quote coin?)
            # Usually we use createOrder API. Let's send a fake 2 USDT market buy.
            # Some exchanges require params={'cost': 2} or similar.
            res = await spot.create_order('TRX/USDT', 'market', 'buy', 2)
            print("Spot Buy Success:", res)
        except Exception as e:
            print(f"Spot Buy Error: {e}")
            
        print("\n--- Testing Swap Open Short (linear) ---")
        try:
            # Test linear open short with 1 contract
            res = await swap.create_order('TRX/USDT:USDT', 'market', 'sell', 1)
            print("Swap Sell Success:", res)
        except Exception as e:
            print(f"Swap Sell Error: {e}")
            
    finally:
        await spot.close()
        await swap.close()

if __name__ == "__main__":
    asyncio.run(test_gate_trade())
