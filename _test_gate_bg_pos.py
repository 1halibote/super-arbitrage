import asyncio
import logging
from backend.execution.exchange_client import ExchangeClient

logging.basicConfig(level=logging.INFO)

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    # Check Gate Linear
    gate_c = ec.get_client('gate_linear')
    if gate_c:
        print("--- Gate Positions ---")
        try:
            pos = await gate_c.fetch_positions()
            for p in pos:
                print(f"Gate Pos: {p.get('symbol')} side={p.get('side')} amt={p.get('contracts')} info={p.get('info')}")
        except Exception as e:
            print(f"Gate error: {e}")
            
    # Check Bitget Linear
    bg_c = ec.get_client('bitget_linear')
    if bg_c:
        print("\n--- Bitget Positions ---")
        try:
            pos = await bg_c.fetch_positions()
            for p in pos:
                print(f"BG Pos: {p.get('symbol')} side={p.get('side')} amt={p.get('contracts')} info={p.get('info')}")
        except Exception as e:
            print(f"BG error: {e}")

asyncio.run(test())
