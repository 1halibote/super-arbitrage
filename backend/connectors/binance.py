import asyncio
import json
import logging
import websockets
from typing import Callable, List

class BinanceClient:
    def __init__(self, callback: Callable, loop: asyncio.AbstractEventLoop):
        self.callback = callback
        self.loop = loop
        # Spot URL
        self.ws_url = "wss://stream.binance.com:9443/stream?streams=!bookTicker"
        self.running = False
        self.ws = None

    async def connect(self):
        self.running = True
        # Subscribe to !ticker@arr (All Market Tickers - 1s update)
        # More stable than !bookTicker for full market view
        self.ws_url = "wss://stream.binance.com:443/stream?streams=!ticker@arr"
        
        while self.running:
            try:
                logging.info(f"Connecting to Binance Spot WS: {self.ws_url}")
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self.ws = ws
                    logging.info("Binance Spot Connected")
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if "data" in data and "!ticker@arr" in data["stream"]:
                            payload = data["data"] 
                            # Payload is a LIST of tickers
                            for item in payload:
                                symbol = item["s"].upper()
                                # Only process USDT pairs
                                if not symbol.endswith("USDT"):
                                    continue
                                ticker = {
                                    "exchange": "binance",
                                    "symbol": symbol,
                                    "bid": float(item["b"]),
                                    "ask": float(item["a"]),
                                    "volume": float(item.get("q", 0)), # Quote Volume (USDT turnover)
                                    "timestamp": asyncio.get_running_loop().time()
                                }
                                await self.callback(ticker)

            except Exception as e:
                logging.error(f"Binance Spot connection error: {e}")
                await asyncio.sleep(5)  # Reconnect delay

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()

class BinanceFutureClient:
    def __init__(self, callback: Callable, loop: asyncio.AbstractEventLoop):
        self.callback = callback
        self.loop = loop
        # Futures URL handled in connect
        self.ws_url = "wss://fstream.binance.com/stream" 
        self.running = False
        self.ws = None

    async def connect(self):
        self.running = True
        self.funding_limits = {}
        
        # Start background task for funding limits
        asyncio.create_task(self._fetch_funding_limits_periodically())
        
        # ALL Symbols Strategy
        # Spot: !bookTicker + !miniTicker@arr (for volume)
        # Future: !bookTicker + !markPrice@arr@1s (for funding/index) + !miniTicker@arr (for volume? or markPrice has it? MarkPrice doesn't have vol. Futures needs miniTicker or ticker for Volume)
        
        streams = []
        if "fstream" in self.ws_url: # Future
            # !ticker@arr contains volume (q) and is 1s update? !miniTicker is also fine.
            # Let's use !miniTicker@arr for volume to save bandwidth, !bookTicker for speed.
            streams = ["!bookTicker", "!markPrice@arr@1s", "!miniTicker@arr"]
            base_url = "wss://fstream.binance.com/stream?streams="
        else: # Spot
            streams = ["!bookTicker", "!miniTicker@arr"]
            base_url = "wss://stream.binance.com:9443/stream?streams="
            
        self.ws_url = base_url + "/".join(streams)

        while self.running:
            try:
                logging.info(f"Connecting to Binance Global WS: {self.ws_url}")
                async with websockets.connect(self.ws_url) as ws:
                    logging.info("Binance Global Connected")
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if "data" in data:
                            payload = data["data"]
                            stream = data["stream"]
                            
                            current_time = asyncio.get_running_loop().time()

                            # 1. MARK PRICE Stream (Futures Only)
                            # Payload list
                            if "!markPrice@arr@1s" in stream:
                                for item in payload:
                                    # "r": Funding Rate
                                    # "T": Next Funding Time (timestamp)
                                    # "i": Index Price
                                    funding_time = item.get("T", 0)
                                    # Calc interval in hours
                                    # Default 8h if 0?
                                    
                                    limits = self.funding_limits.get(item["s"], {"max": 0, "min": 0})
                                    
                                    update_data = {
                                        "exchange": "binance_future",
                                        "symbol": item["s"],
                                        "fundingRate": float(item.get("r", 0)),
                                        "indexPrice": float(item.get("i", 0)),
                                        "markPrice": float(item.get("p", 0)),
                                        "nextFundingTime": funding_time,
                                        "fundingMax": limits["max"],
                                        "fundingMin": limits["min"],
                                        "fundingInterval": limits.get("interval", 8),
                                        "timestamp": current_time
                                    }
                                    await self.callback(update_data)
                                continue
                            
                            # 2. MINI TICKER Stream (Volume)
                            # Payload list
                            # Spot miniTicker: "q": quote volume
                            if "!miniTicker@arr" in stream:
                                for item in payload:
                                    symbol = item["s"]
                                    # Only process USDT pairs
                                    if not symbol.endswith("USDT"):
                                        continue
                                    ex_name = "binance_future" if "fstream" in self.ws_url else "binance"
                                    # "q" is Quote Volume (USDT volume)
                                    vol = float(item.get("q", 0))
                                    update_data = {
                                        "exchange": ex_name,
                                        "symbol": symbol,
                                        "volume": vol,
                                        "timestamp": current_time
                                    }
                                    await self.callback(update_data)
                                continue

                            # 3. BOOK TICKER Stream (Price Spreads - Latency Critical)
                            # Payload object (not list usually, but wrapped in stream it might be object)
                            symbol = payload["s"].upper()
                            # Only process USDT pairs
                            if not symbol.endswith("USDT"):
                                continue
                            ex_name = "binance_future" if "fstream" in self.ws_url else "binance"
                            
                            ticker = {
                                "exchange": ex_name,
                                "symbol": symbol,
                                "bid": float(payload["b"]),
                                "ask": float(payload["a"]),
                                "timestamp": current_time
                            }
                            await self.callback(ticker)

            except Exception as e:
                logging.error(f"Binance connection error: {e}")
                await asyncio.sleep(5)

    async def _fetch_funding_limits_periodically(self):
        import aiohttp
        while self.running:
            try:
                # Use aiohttp for non-blocking HTTP
                async with aiohttp.ClientSession(trust_env=True) as session:
                    async with session.get("https://fapi.binance.com/fapi/v1/fundingInfo") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # data is a list of objects
                            count = 0
                            for item in data:
                                # item: {"symbol": "BTCUSDT", "adjustedFundingRateCap": "0.02", "adjustedFundingRateFloor": "-0.02", ...}
                                s = item["symbol"]
                                self.funding_limits[s] = {
                                    "max": float(item.get("adjustedFundingRateCap", 0)),
                                    "min": float(item.get("adjustedFundingRateFloor", 0)),
                                    "interval": int(item.get("fundingIntervalHours", 8))
                                }
                                count += 1
                            logging.info(f"Binance Futures: Fetched {count} funding limits")
            except Exception as e:
                logging.error(f"Binance fetch limits error: {e}")
            
            await asyncio.sleep(300) # Every 5 minutes

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
