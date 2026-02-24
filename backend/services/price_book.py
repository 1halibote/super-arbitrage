from typing import Dict, Optional

class PriceBook:
    def __init__(self):
        # Storage: { "BTCUSDT": { "binance": ticker_obj, "bybit_spot": ticker_obj, ... } }
        self.prices: Dict[str, Dict[str, dict]] = {}
        # 记录每个交易所最后的全局更新时间，用于检测断连
        self.exchange_heartbeats: Dict[str, float] = {}

    def update(self, ticker: dict):
        symbol = ticker.get("symbol")
        exchange = ticker.get("exchange")
        if not symbol or not exchange: return
        
        import time
        now = time.time()
        self.exchange_heartbeats[exchange] = now
        ticker['_local_timestamp'] = now
        
        if symbol not in self.prices:
            self.prices[symbol] = {}
        
        if exchange not in self.prices[symbol]:
            self.prices[symbol][exchange] = {}
            
        self.prices[symbol][exchange].update(ticker)

    def get_snapshot(self):
        return self.prices

    def get_ticker(self, symbol: str, exchange: str) -> Optional[dict]:
        """Get latest ticker for specific exchange"""
        return self.prices.get(symbol, {}).get(exchange)

    def clear_stale_exchanges(self, timeout_seconds=60) -> list:
        """
        清理已死掉/假死的交易所数据。
        如果某交易所超过 timeout_seconds 没有任何 ticker 更新，说明 WS 已断连。
        返回被清理的交易所列表。
        """
        import time
        now = time.time()
        stale_exchanges = []
        
        for ex, last_time in list(self.exchange_heartbeats.items()):
            if now - last_time > timeout_seconds:
                stale_exchanges.append(ex)
                
        if stale_exchanges:
            # 清理所有价格本中的这些交易所数据
            for sym, exchanges in list(self.prices.items()):
                for ex in stale_exchanges:
                    if ex in exchanges:
                        del exchanges[ex]
                # 如果这个币种下面没有交易所数据了，也可以清理掉（可选）
                if not exchanges:
                    del self.prices[sym]
                    
            # 从心跳记录中移除，直到它重连再次报活
            for ex in stale_exchanges:
                del self.exchange_heartbeats[ex]
                
        return stale_exchanges
