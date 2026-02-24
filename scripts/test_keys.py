import json
from backend.services.arbitrage import ArbitrageCalculator
from backend.services.price_book import PriceBook

def test_keys():
    pb = PriceBook()
    pb.update({
        "exchange": "bybit_spot", 
        "symbol": "SOLUSDT", 
        "bid": 83.66, "ask": 83.67, 
        "lastPrice": 83.66, "timestamp": 123
    })
    pb.update({
        "exchange": "bybit_linear", 
        "symbol": "SOLUSDT", 
        "bid": 83.66, "ask": 83.67, 
        "lastPrice": 83.66, "timestamp": 123
    })
    pb.update({
        "exchange": "binance_future", 
        "symbol": "SOLUSDT", 
        "bid": 83.66, "ask": 83.67, 
        "lastPrice": 83.66, "timestamp": 123
    })
    
    calc = ArbitrageCalculator(pb)
    res_sf = calc.calculate_sf()
    print("SF Pairs Generated:")
    for r in res_sf:
        print(r['pair'])
        
    res_ff = calc.calculate_ff()
    print("FF Pairs Generated:")
    for r in res_ff:
        print(r['pair'])

    print("\nMonitor get_key rules:")
    def get_key(ex, ts):
        if ex == 'binance':
            return 'binance_future' if ts == 'linear' else 'binance'
        elif ex == 'bybit':
            return 'bybit_linear' if ts == 'linear' else 'bybit_spot'
        return f"{ex}_{ts}"
        
    print("SF(BY/BY) pair expected in monitor:", f"{get_key('bybit', 'spot')}/{get_key('bybit', 'linear')}")
    print("SF(BN/BN) pair expected in monitor:", f"{get_key('binance', 'spot')}/{get_key('binance', 'linear')}")
    print("FF(BN/BY) pair expected in monitor:", f"{get_key('binance', 'linear')}/{get_key('bybit', 'linear')}")

if __name__ == '__main__':
    test_keys()
