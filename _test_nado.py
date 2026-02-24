import asyncio, sys, logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from backend.connectors.nado import NadoClient
from backend.services.price_book import PriceBook

price_book = PriceBook()

async def ticker_callback(ticker):
    price_book.update(ticker)

async def main():
    c = NadoClient("", "default")
    c.set_ticker_callback(ticker_callback)
    await c.init()

    snap = price_book.get_snapshot()
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        if sym in snap:
            for ex_name, data in snap[sym].items():
                if "nado" in ex_name:
                    bid = data.get('bid', 0)
                    ask = data.get('ask', 0)
                    fr = data.get('fundingRate', 0)
                    fi = data.get('fundingInterval', 'N/A')
                    vol = data.get('volume', 0)
                    idx = data.get('indexPrice', 0)
                    mk = data.get('markPrice', 0)
                    print(f"{sym} @ {ex_name}:")
                    print(f"  bid={bid:.2f}  ask={ask:.2f}")
                    print(f"  fundingRate={fr*100:.6f}%  interval={fi}h")
                    print(f"  volume=${vol:,.0f}")
                    print(f"  indexPrice={idx:.2f}  markPrice={mk:.2f}")
                    if idx > 0 and mk > 0:
                        spread = (mk - idx) / idx * 100
                        print(f"  indexSpread={spread:.6f}%")
                    print()

    await c.close()

asyncio.run(main())
