import asyncio
import json
import logging
import websockets
from typing import Callable, List

import aiohttp

class BybitClient:
    def __init__(self, category: str, callback: Callable, loop: asyncio.AbstractEventLoop):
        # category: "spot" or "linear"
        self.category = category
        self.callback = callback
        self.loop = loop
        
        if category == "spot":
            self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        else: 
            self.ws_url = "wss://stream.bybit.com/v5/public/linear"
            
        # Optional: Use HK/International optimized endpoints if needed
        # self.ws_url = self.ws_url.replace("stream.bybit.com", "stream.bybit.com") 
            
        self.running = False
        self.ws = None
        self.symbols = [] # To be populated via API

    async def fetch_symbols(self):
        """Fetch active USDT symbols from Bybit API"""
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {
            "category": self.category,
            "status": "Trading",
            "limit": 1000 # Max limit
        }
        
        if self.category == "linear":
            # Just grab USDT pairs
            all_syms = []
            cursor = ""
            # Enable trust_env to use system HTTP_PROXY/HTTPS_PROXY
            async with aiohttp.ClientSession(trust_env=True) as session:
                while True:
                    p = params.copy()
                    if cursor: p["cursor"] = cursor
                    
                    async with session.get(url, params=p) as resp:
                        data = await resp.json()
                        if data["retCode"] == 0:
                            for item in data["result"]["list"]:
                                if item["symbol"].endswith("USDT"):
                                    all_syms.append(item["symbol"])
                            
                            cursor = data["result"].get("nextPageCursor", "")
                            if not cursor:
                                break
                        else:
                            break
            self.symbols = all_syms
            
            # HOTFIX: Bybit API sometimes omits MEGAUSDT from the list despite it being valid.
            # We manually ensure it's present for subscription.
            if "MEGAUSDT" not in self.symbols:
                self.symbols.append("MEGAUSDT")
                logging.info("Forced MEGAUSDT into Linear symbols")
                
            logging.info(f"Bybit {self.category}: Found {len(self.symbols)} USDT symbols")
            
        elif self.category == "spot":
             # Spot USDT pairs
            all_syms = []
            async with aiohttp.ClientSession(trust_env=True) as session:
                 # Pagination needed if > 1000, usually spot is > 1000
                 cursor = ""
                 while True:
                    p = params.copy()
                    if cursor: p["cursor"] = cursor
                    async with session.get(url, params=p) as resp:
                        data = await resp.json()
                        if data["retCode"] == 0:
                            for item in data["result"]["list"]:
                                if item["symbol"].endswith("USDT"):
                                    all_syms.append(item["symbol"])
                            cursor = data["result"].get("nextPageCursor", "")
                            if not cursor:
                                break
                        else:
                             break
            self.symbols = all_syms
            logging.info(f"Bybit {self.category}: Found {len(self.symbols)} USDT symbols")

    async def connect(self):
        self.running = True
        self.funding_limits = {}
        if self.category == "linear":
            asyncio.create_task(self._fetch_funding_limits_periodically())
        
        # 1. Fetch symbols first
        # 1. Fetch symbols first (Retry loop)
        while self.running and not self.symbols:
            try:
                await self.fetch_symbols()
                if not self.symbols:
                    logging.warning(f"Bybit {self.category}: No symbols found. Retrying in 5s...")
                    await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Bybit {self.category} fetch symbols failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
        
        if not self.running:
            return

        while self.running:
            try:
                logging.info(f"Connecting to Bybit {self.category.title()} WS")
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    logging.info(f"Bybit {self.category.title()} Connected")
                    
                    # 2. Batch Subscribe (Aggressive throttling for Bybit stability)
                    if self.category == "linear":
                        chunk_size = 10
                        # Linear: subscribe to tickers (contains bid1Price/ask1Price)
                        for i in range(0, len(self.symbols), chunk_size):
                            chunk = self.symbols[i:i+chunk_size]
                            req = {
                                "op": "subscribe",
                                "args": [f"tickers.{s}" for s in chunk]
                            }
                            await ws.send(json.dumps(req))
                            await asyncio.sleep(0.3) # Increased delay to avoid buffer overflow
                    else:
                        # Spot: Need BOTH orderbook (for bid/ask) and tickers (for volume)
                        chunk_size = 5 # Reduced chunk size because we are subscribing to 2 topics per symbol
                        for i in range(0, len(self.symbols), chunk_size):
                            chunk = self.symbols[i:i+chunk_size]
                            # Subscribe to both topics at once
                            args = []
                            for s in chunk:
                                args.append(f"orderbook.1.{s}")
                                args.append(f"tickers.{s}")
                                
                            req = {
                                "op": "subscribe",
                                "args": args
                            }
                            await ws.send(json.dumps(req))
                            await asyncio.sleep(0.3)
                    
                    logging.info(f"Bybit {self.category}: Initial subscription flood finished.")
                    
                    # Heartbeat task
                    heartbeat = asyncio.create_task(self._heartbeat(ws))
                    
                    try:
                        while self.running:
                            msg = await ws.recv()
                            data = json.loads(msg)
                            
                            if "topic" in data and "data" in data:
                                # Bybit V5 Ticker format
                                # Spot: data is atomic or list? V5 spot ticker is push.
                                # Linear: data is atomic or list?
                                # Usually 'data': {...} or 'data': [{...}]
                                # "topic": "tickers.BTCUSDT"
                                topic = data["topic"]
                                payload = data["data"]
                                
                                # Bybit Ticker Data Structure
                                # Spot: { "s": "BTCUSDT", "bp1": "...", "ap1": "..." }
                                # Linear: { "symbol": "BTCUSDT", "bid1Price": "...", "ask1Price": "..." }
                                
                                symbol = topic.split('.')[-1]
                                
                                bid = 0.0
                                ask = 0.0
                                last = 0.0
                                
                                # LOGIC FOR ORDERBOOK (Spot/Linear shared if snapshot)
                                if "orderbook" in topic:
                                    # payload: { "s": "BTCUSDT", "b": [["price", "size"]], "a": [...] }
                                    if "b" in payload and payload["b"]:
                                        bid = float(payload["b"][0][0])
                                    if "a" in payload and payload["a"]:
                                        ask = float(payload["a"][0][0])
                                        
                                # LOGIC FOR TICKERS (V5 Spot & Linear use same fields)
                                else:
                                    # Both Spot and Linear use bid1Price/ask1Price in V5
                                    if "bid1Price" in payload and payload["bid1Price"]:
                                        try: bid = float(payload["bid1Price"])
                                        except: pass
                                    if "ask1Price" in payload and payload["ask1Price"]:
                                        try: ask = float(payload["ask1Price"])
                                        except: pass
                                    if "lastPrice" in payload and payload["lastPrice"]:
                                        try: last = float(payload["lastPrice"])
                                        except: pass
                                
                                # Construct ticker with ONLY present fields to avoid overwriting state with 0
                                ticker = {
                                    "exchange": f"bybit_{self.category}", 
                                    "symbol": symbol,
                                    "timestamp": asyncio.get_running_loop().time()
                                }
                                
                                if bid > 0: ticker["bid"] = bid
                                if ask > 0: ticker["ask"] = ask
                                if last > 0: ticker["lastPrice"] = last
                                
                                # Conditional fields
                                if self.category == "linear":
                                    if "fundingRate" in payload:
                                        ticker["fundingRate"] = float(payload["fundingRate"])
                                    if "turnover24h" in payload:
                                        ticker["volume"] = float(payload["turnover24h"])
                                    if "indexPrice" in payload:
                                        ticker["indexPrice"] = float(payload["indexPrice"])
                                    if "markPrice" in payload:
                                        ticker["markPrice"] = float(payload["markPrice"])
                                    if "nextFundingTime" in payload:
                                        ticker["nextFundingTime"] = int(payload["nextFundingTime"])
                                    
                                    # Inject Limits
                                    if hasattr(self, 'funding_limits'):
                                        limits = self.funding_limits.get(symbol, {"max": 0, "min": 0})
                                        ticker["fundingMax"] = limits["max"]
                                        ticker["fundingMin"] = limits["min"]
                                        ticker["fundingInterval"] = limits.get("interval", 8)
                                else:
                                    # Spot Volume
                                    if "turnover24h" in payload:
                                        ticker["volume"] = float(payload["turnover24h"])

                                await self.callback(ticker)
                                    
                    except Exception as e:
                        if "no close frame" in str(e) or "1006" in str(e):
                             logging.warning(f"Bybit {self.category} disconnected (retry): {e}")
                        else:
                             logging.error(f"Bybit {self.category} recv error: {e}")
                    finally:
                        heartbeat.cancel()
                        
            except Exception as e:
                logging.error(f"Bybit {self.category} connection error: {e}")
                await asyncio.sleep(5)

    async def _heartbeat(self, ws):
        while True:
            await asyncio.sleep(20)
            try:
                await ws.send(json.dumps({"op": "ping"}))
            except:
                break

    async def _fetch_funding_limits_periodically(self):
        if self.category != "linear": return
        import aiohttp
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {"category": "linear", "limit": 1000, "status": "Trading"}
        
        while self.running:
            try:
                # Need pagination for Bybit Linear (has > 200 symbols)
                limits_map = {}
                cursor = ""
                
                async with aiohttp.ClientSession(trust_env=True) as session:
                    while True:
                        p = params.copy()
                        if cursor: p["cursor"] = cursor
                        async with session.get(url, params=p) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data["retCode"] == 0:
                                    for item in data["result"].get("list", []):
                                        s = item["symbol"]
                                        # Convert fundingInterval (minutes) to hours (default 8h if missing)
                                        interval_min = int(item.get("fundingInterval", 480))
                                        interval_hours = interval_min // 60
                                        
                                        limits_map[s] = {
                                            "max": float(item.get("upperFundingRate", 0)),
                                            "min": float(item.get("lowerFundingRate", 0)),
                                            "interval": interval_hours
                                        }
                                    
                                    cursor = data["result"].get("nextPageCursor", "")
                                    if not cursor:
                                        break
                                else:
                                    break
                            else:
                                break
                                
                self.funding_limits = limits_map
                logging.info(f"Bybit Linear: Fetched {len(limits_map)} funding limits")
            except Exception as e:
                logging.error(f"Bybit fetch limits error: {e}")
            
            await asyncio.sleep(300)

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
