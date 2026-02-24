import asyncio
from backend.execution.exchange_client import exchange_client
from backend.execution.key_store import api_key_store
import json

async def run():
    await exchange_client.initialize()
    
    # Check Bybit
    print("--- Bybit ---")
    pos_bybit = exchange_client._exchanges.get("bybit_linear")
    if pos_bybit:
        all_pos = await pos_bybit.fetch_positions(params={'category': 'linear', 'limit': 100})
        if all_pos:
            print(json.dumps(all_pos[0]['info'], indent=2))
        else:
            print("No bybit linear positions")
            
    # Check Bitget
    print("--- Bitget ---")
    pos_bitget = exchange_client._exchanges.get("bitget_linear")
    if pos_bitget:
        all_pos = await pos_bitget.fetch_positions(params={'productType': 'USDT-FMC'})
        if all_pos:
            print(json.dumps(all_pos[0]['info'], indent=2))
        else:
            print("No bitget linear positions")

    # Check Gate
    print("--- Gate ---")
    pos_gate = exchange_client._exchanges.get("gate_linear")
    if pos_gate:
        all_pos = await pos_gate.fetch_positions()
        if all_pos:
            print(json.dumps(all_pos[0]['info'], indent=2))
        else:
            print("No gate linear positions")

asyncio.run(run())
