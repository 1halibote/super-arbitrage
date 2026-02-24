import asyncio
import os
import sys

# 注入项目根目录到 PATH
sys.path.insert(0, os.path.abspath('.'))

from backend.execution.exchange_client import exchange_client
from backend.execution.key_store import api_key_store

async def test_bitget():
    # 模拟启动
    await exchange_client.initialize()
    
    bg_linear = exchange_client.get_client("bitget_linear")
    if not bg_linear:
        print("未找到 bitget_linear 实例！请先在页面上配置。")
        return
        
    print("----- 正在请求 Bitget 仓位 -----")
    try:
        positions = await bg_linear.fetch_positions(params={'productType': 'USDT-FUTURES'})
        for p in positions:
            if p['symbol'] == 'BTC/USDT:USDT' or float(p.get('contracts', 0) or 0) > 0:
                print("\nParsed Position:")
                print({k: v for k, v in p.items() if k != 'info'})
                print("\nRaw Info:")
                print(p.get('info'))
                break
        else:
            if positions:
                print("Raw Info (First Pos):", positions[0].get('info'))
            else:
                print("没有获取到任何仓位。")
    except Exception as e:
        print("获取仓位报错:", e)

    print("\n----- 正在尝试设置杠杆 ----")
    try:
        # 给某个没人交易但存在的币种设杠杆
        sym = 'XRP/USDT:USDT'
        res = await bg_linear.set_leverage(5, sym, params={'marginCoin': 'USDT', 'productType': 'USDT-FUTURES'})
        print(f"XRP Leverage set to 5x: {res}")
    except Exception as e:
        print(f"Leverage Set Error: {e}")

    await exchange_client.shutdown()

if __name__ == "__main__":
    asyncio.run(test_bitget())
