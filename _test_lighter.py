import asyncio, sys, logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from backend.connectors.lighter import LighterClient
from backend.services.price_book import PriceBook

price_book = PriceBook()
count = 0

async def ticker_callback(ticker):
    global count
    price_book.update(ticker)
    count += 1

async def main():
    global count
    c = LighterClient()
    c.set_ticker_callback(ticker_callback)
    await c.init()

    ws_task = asyncio.create_task(c.run_ws())
    # 等 15 秒确保 market_stats 也推送了
    await asyncio.sleep(15)
    ws_task.cancel()

    snap = price_book.get_snapshot()
    print(f"\nPriceBook: {len(snap)} symbols, {count} callbacks")
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]:
        if sym in snap:
            for ex_name, data in snap[sym].items():
                if "lighter" in ex_name:
                    bid = data.get('bid', 0)
                    ask = data.get('ask', 0)
                    fr = data.get('fundingRate', 0)
                    fi = data.get('fundingInterval', 'N/A')
                    vol = data.get('volume', 0)
                    idx = data.get('indexPrice', 0)
                    mk = data.get('markPrice', 0)
                    print(f"\n{sym} @ {ex_name}:")
                    print(f"  bid={bid:.2f}  ask={ask:.2f}")
                    print(f"  fundingRate={fr*100:.6f}%  interval={fi}h")
                    print(f"  volume=${vol:,.0f}")
                    print(f"  indexPrice={idx:.2f}  markPrice={mk:.2f}")
                    if idx > 0 and mk > 0:
                        spread = (mk - idx) / idx * 100
                        print(f"  indexSpread={spread:.6f}%")

    await c.close()

asyncio.run(main())
