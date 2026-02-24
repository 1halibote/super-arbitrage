import asyncio
import ccxt.async_support as ccxt
from backend.execution.exchange_client import ExchangeClient

async def test():
    ec = ExchangeClient()
    await ec.initialize()
    
    amount_usdt = 20.0
    price_a = 0.03304  # 假设 AZTEC 价格
    price_b = 0.03304
    
    avg_price = (price_a + price_b) / 2
    raw_qty = amount_usdt / avg_price
    print(f"raw_qty: {raw_qty} AZTEC")
    
    amount_a = raw_qty
    amount_b = raw_qty
    
    final_qty = min(amount_a, amount_b)
    amount_a = amount_b = final_qty
    print(f"Align min: {amount_a}")
    
    # 模拟 convert_and_format
    client_a = ec.get_client('gate_linear')
    client_b = ec.get_client('bybit_linear')
    
    def convert(c, k, sym, amt):
        try:
            if 'gate' in k and 'spot' not in k:
                cs = c.market(sym).get('contractSize', 1)
                conts = amt / cs
                return float(c.amount_to_precision(sym, conts)), 'contracts'
            return float(c.amount_to_precision(sym, amt)), 'coins'
        except Exception as e:
            return amt, 'error'
            
    res_a, unit_a = convert(client_a, 'gate_linear', 'AZTEC/USDT:USDT', amount_a)
    res_b, unit_b = convert(client_b, 'bybit_linear', 'AZTEC/USDT:USDT', amount_b)
    
    print(f"Gate Linear: {res_a} {unit_a}")
    print(f"Bybit Linear: {res_b} {unit_b}")

asyncio.run(test())
