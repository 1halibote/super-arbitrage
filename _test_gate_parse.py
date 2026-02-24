import asyncio
import json
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    gc = ec.get_client('gate_linear')
    if gc:
        try:
            pos = await gc.fetch_positions()
            for p in pos:
                amt = p.get('contracts') or p.get('positionAmt')
                if float(amt or 0) != 0:
                    sym = p.get('symbol')
                    print(f"\n--- Raw Pos Data for {sym} ---")
                    print(json.dumps(p, indent=2))
                    
                    # 模拟 parse_position_list 处理
                    print(f"\n--- parse_position_list outputs ---")
                    # target_side 分别试 long 和 short 和 None
                    for ts in [None, 'long', 'short']:
                        res = ec.parse_position_list([p], sym, target_side=ts)
                        print(f"target_side={ts}: qty={res[0]}, val={res[1]}, price={res[2]}, pnl={res[3]}, liq={res[4]}")
                        
        except Exception as e:
            print(f"Gate error: {e}")

asyncio.run(test())
