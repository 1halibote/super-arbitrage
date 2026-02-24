import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from backend.execution.exchange_client import exchange_client

async def test_fetch_pos():
    await exchange_client.initialize()
    bg = exchange_client.get_client("bitget_linear")
    if not bg: return

    # 查询真实的持仓
    # 用户现在有1020 U的合约和 2666的现货，里面应当有开出的仓位
    try:
        # bitget fetchPositions
        positions = await bg.fetch_positions(params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'})
        for p in positions:
            if float(p.get('contracts', 0) or 0) > 0 or float(p['info'].get('total', 0) or 0) > 0:
                print(f"--- Pos: {p['symbol']} ---")
                print("CCXT Output keys:", list(p.keys()))
                print("Contracts:", p.get('contracts'))
                print("Info Dict:")
                for k, v in p['info'].items():
                    print(f"  {k}: {v}")
                break
    except Exception as e:
        print("fetch pos fail:", e)

    await exchange_client.shutdown()

asyncio.run(test_fetch_pos())
