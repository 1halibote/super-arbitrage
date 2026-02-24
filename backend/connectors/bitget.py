import asyncio
import json
import logging
import websockets
from typing import Callable
import aiohttp

class BitgetClient:
    """Bitget UTA (V3) WebSocket 行情客户端"""
    
    def __init__(self, category: str, callback: Callable, loop: asyncio.AbstractEventLoop):
        # category: "spot" or "linear"
        self.category = category
        self.callback = callback
        self.loop = loop
        self.ws_url = "wss://ws.bitget.com/v3/ws/public"
        self.running = False
        self.ws = None
        self.symbols = []
        self.msg_count = 0
        self.ticker_count = 0
        self.funding_limits = {}  # {"BTCUSDT": {"interval": 8, "max": 0.003, "min": -0.003}}
        
        # UTA instType 映射
        self._inst_type = "usdt-futures" if category == "linear" else "spot"
        # PriceBook exchange key
        self._exchange_key = f"bitget_{category}"
        
    async def fetch_symbols(self):
        if self.category == "linear":
            url = "https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES"
        else:
            url = "https://api.bitget.com/api/v2/spot/public/symbols"
            
        all_syms = []
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if data.get("code") == "00000" and "data" in data:
                        for item in data["data"]:
                            symbol = item.get("symbol", "")
                            if self.category == "linear":
                                all_syms.append(symbol)
                            else:
                                if item.get("status") == "online" and symbol.endswith("USDT"):
                                    all_syms.append(symbol)
        except Exception as e:
            logging.error(f"[Bitget {self.category}] fetch_symbols error: {e}")
            
        self.symbols = all_syms
        logging.info(f"[Bitget {self.category}] Found {len(self.symbols)} USDT symbols")

    async def connect(self):
        self.running = True
        
        while self.running and not self.symbols:
            try:
                await self.fetch_symbols()
                if not self.symbols:
                    logging.warning(f"[Bitget {self.category}] No symbols, retrying in 5s...")
                    await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"[Bitget {self.category}] fetch failed: {e}, retrying in 5s...")
                await asyncio.sleep(5)
        
        if not self.running:
            return

        while self.running:
            try:
                logging.info(f"[Bitget {self.category}] Connecting WS...")
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    logging.info(f"[Bitget {self.category}] WS Connected")
                    
                    # 先启动 ping 保活
                    ping_task = asyncio.create_task(self._ping_loop())
                    # 合约模式：先同步加载 funding limits，再订阅 WS
                    funding_task = None
                    if self.category == "linear":
                        await self._fetch_funding_info_once()
                        funding_task = asyncio.create_task(self._fetch_funding_info())
                    
                    # V3/UTA 批量订阅，每批 50 个，间隔极短
                    chunk_size = 50
                    for i in range(0, len(self.symbols), chunk_size):
                        chunk = self.symbols[i:i+chunk_size]
                        args = [{"instType": self._inst_type, "topic": "ticker", "symbol": s} for s in chunk]
                        await ws.send(json.dumps({"op": "subscribe", "args": args}))
                        # 每批之间短暂让出控制权，消化 pending 消息
                        await asyncio.sleep(0.05)
                    
                    logging.info(f"[Bitget {self.category}] Subscribed {len(self.symbols)} symbols")
                    
                    try:
                        while self.running:
                            msg = await ws.recv()
                            if msg == "pong":
                                continue
                            self.msg_count += 1
                            data = json.loads(msg)
                            
                            action = data.get("action")
                            event = data.get("event")
                            
                            if self.msg_count <= 3:
                                logging.info(f"[Bitget {self.category}] MSG#{self.msg_count}: action={action} event={event} keys={list(data.keys())}")
                            
                            if action == "snapshot" and "data" in data:
                                await self._handle_ticker(data)
                            elif event == "error":
                                logging.error(f"[Bitget {self.category}] WS Error: {data}")
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning(f"[Bitget {self.category}] WS Closed, reconnecting...")
                    except Exception as e:
                        logging.error(f"[Bitget {self.category}] WS error: {e}")
                    finally:
                        ping_task.cancel()
                        if funding_task: funding_task.cancel()
            except Exception as e:
                logging.error(f"[Bitget {self.category}] Connect error: {e}")
                await asyncio.sleep(5)

    async def _handle_ticker(self, data):
        for t in data["data"]:
            symbol = t.get("symbol") or data.get("arg", {}).get("symbol")
            if not symbol:
                continue
            
            bid = float(t.get("bid1Price", 0) or 0)
            ask = float(t.get("ask1Price", 0) or 0)
            if bid <= 0 or ask <= 0:
                continue
            
            self.ticker_count += 1
            if self.ticker_count == 1:
                logging.info(f"[Bitget {self.category}] FIRST TICKER: {symbol} bid={bid} ask={ask}")
            
            ticker = {
                "symbol": symbol,
                "exchange": self._exchange_key,
                "bid": bid,
                "ask": ask,
                "lastPrice": float(t.get("lastPrice", 0) or 0),
            }
            
            # 合约特有数据
            if self.category == "linear":
                fr = t.get("fundingRate")
                if fr: ticker["fundingRate"] = float(fr)
                mp = t.get("markPrice")
                if mp: ticker["markPrice"] = float(mp)
                ip = t.get("indexPrice")
                if ip: ticker["indexPrice"] = float(ip)
                nft = t.get("nextFundingTime")
                if nft: ticker["nextFundingTime"] = float(nft)
                
                # 从 REST 缓存附加 funding limits
                limits = self.funding_limits.get(symbol, {})
                if limits:
                    ticker["fundingInterval"] = limits.get("interval", 8)
                    ticker["fundingMax"] = limits.get("max", 0)
                    ticker["fundingMin"] = limits.get("min", 0)
            
            # 成交量
            vol = t.get("turnover24h") or t.get("volume24h")
            if vol: ticker["volume"] = float(vol)
            
            await self.callback(ticker)

    async def _fetch_funding_info_once(self):
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                url = "https://api.bitget.com/api/v2/mix/market/current-fund-rate?productType=USDT-FUTURES"
                async with session.get(url) as resp:
                    data = await resp.json()
                    if data.get("code") == "00000" and data.get("data"):
                        for item in data["data"]:
                            try:
                                s = item.get("symbol", "")
                                if not s: continue
                                interval_str = item.get("fundingRateInterval")
                                interval = int(interval_str) if interval_str else 8
                                max_str = item.get("maxFundingRate")
                                fr_max = float(max_str) if max_str else 0.0
                                min_str = item.get("minFundingRate")
                                fr_min = float(min_str) if min_str else 0.0
                                
                                self.funding_limits[s] = {
                                    "interval": interval,
                                    "max": fr_max,
                                    "min": fr_min,
                                }
                            except Exception as parse_e:
                                logging.debug(f"[Bitget linear] Parse funding limit error for {item}: {parse_e}")
                        logging.info(f"[Bitget linear] Pre-loaded {len(self.funding_limits)} funding limits")
        except Exception as e:
            logging.error(f"[Bitget linear] Pre-load funding info error: {e}")

    async def _fetch_funding_info(self):
        while self.running:
            try:
                async with aiohttp.ClientSession(trust_env=True) as session:
                    url = "https://api.bitget.com/api/v2/mix/market/current-fund-rate?productType=USDT-FUTURES"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if data.get("code") == "00000" and data.get("data"):
                            count = 0
                            for item in data["data"]:
                                try:
                                    s = item.get("symbol", "")
                                    if not s: continue
                                    interval_str = item.get("fundingRateInterval")
                                    interval = int(interval_str) if interval_str else 8
                                    max_str = item.get("maxFundingRate")
                                    fr_max = float(max_str) if max_str else 0.0
                                    min_str = item.get("minFundingRate")
                                    fr_min = float(min_str) if min_str else 0.0
                                    
                                    self.funding_limits[s] = {
                                        "interval": interval,
                                        "max": fr_max,
                                        "min": fr_min,
                                    }
                                    # 主动推送到 PriceBook
                                    await self.callback({
                                        "symbol": s,
                                        "exchange": self._exchange_key,
                                        "fundingInterval": interval,
                                        "fundingMax": fr_max,
                                        "fundingMin": fr_min,
                                    })
                                    count += 1
                                except Exception as parse_e:
                                    # Skip error items silently or debug
                                    pass
                            logging.info(f"[Bitget linear] Fetched {count} funding limits")
            except Exception as e:
                logging.error(f"[Bitget linear] Fetch funding info error: {e}")
            await asyncio.sleep(300)

    async def _ping_loop(self):
        while self.running and self.ws:
            try:
                await self.ws.send("ping")
                await asyncio.sleep(20)
            except:
                break

    async def stop(self):
        self.running = False
        if self.ws:
            try: await self.ws.close()
            except: pass
