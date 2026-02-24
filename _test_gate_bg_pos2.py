import asyncio
from backend.execution.exchange_client import ExchangeClient

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
                amt = p.get('contracts') or p.get('positionAmt') or p.get('info', {}).get('size')
                if float(amt or 0) != 0:
                    print(f"Gate Pos: {p.get('symbol')} side={p.get('side')} amt={amt} info_size={p.get('info', {}).get('size')}")
        except Exception as e:
            print(f"Gate error: {e}")
            
    # Check Bitget Linear
    bg_c = ec.get_client('bitget_linear')
    if bg_c:
        print("\n--- Bitget Positions ---")
        try:
            pos = await bg_c.fetch_positions()
            for p in pos:
                amt = p.get('contracts', 0)
                if float(amt or 0) != 0:
                    print(f"BG Pos: {p.get('symbol')} side={p.get('side')} amt={amt}")
        except Exception as e:
            print(f"BG error: {e}")

asyncio.run(test())
