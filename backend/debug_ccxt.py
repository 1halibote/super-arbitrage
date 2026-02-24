import asyncio
import ccxt.async_support as ccxt
import json

async def main():
    keys = {}
    with open('f:/xiangmu/bn-by/backend/data/api_keys.json', 'r') as f:
        keys = json.load(f)

    bn_key = keys.get('binance')
    by_key = keys.get('bybit')

    if by_key:
        by = ccxt.bybit({'apiKey': by_key[0], 'secret': by_key[1], 'options': {'defaultType': 'swap'}})
        try:
            res = await by.fetch_positions()
            for r in res:
                size = float(r.get('contracts') or r.get('info', {}).get('size') or 0)
                if size > 0:
                    print(f"Bybit POS: {r['symbol']} side={r['side']} qty={size} avgPrice={r.get('info', {}).get('avgPrice')}")
                    print(f"Raw info: {r.get('info')}")
        except Exception as e:
            print(f"Bybit error: {e}")
        finally:
            await by.close()

    if bn_key:
        bn = ccxt.binance({'apiKey': bn_key[0], 'secret': bn_key[1], 'options': {'defaultType': 'future'}})
        try:
            res = await bn.fetch_positions()
            for r in res:
                size = float(r.get('contracts') or r.get('info', {}).get('positionAmt') or 0)
                if abs(size) > 0:
                    print(f"Binance POS: {r['symbol']} side={r['side']} qty={size} entryPrice={r.get('info', {}).get('entryPrice')}")
                    print(f"Raw info: {r.get('info')}")
        except Exception as e:
            print(f"Binance error: {e}")
        finally:
            await bn.close()

if __name__ == '__main__':
    asyncio.run(main())
