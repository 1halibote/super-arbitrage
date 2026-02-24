import asyncio
import json
import logging
import time
import uuid
import websockets
import aiohttp
from collections import defaultdict
from typing import Dict, Set

# Gate WebSocket Constants
GATE_SPOT_WS = "wss://api.gateio.ws/ws/v4/"
GATE_FUTURE_WS = "wss://fx-ws.gateio.ws/v4/ws/usdt"

class GateClient:
    """
    Gate.io WebSocket 客户端，提供对现货及 USDT 本位永续合约盘口、资金费率的实时监听，
    并在解析后将价格和资金费写入中央 price_book 中。
    """
    def __init__(self, price_book):
        self.price_book = price_book
        
        self.spot_ws = None
        self.future_ws = None
        self.active = False
        self.reconnecting = False
        
        self.spot_symbols: Set[str] = set()
        self.future_symbols: Set[str] = set()
        self.symbols: Set[str] = set()

        # Rate Limiting & Maintenance
        self.ping_interval = 20
        self.last_spot_ping = 0
        self.last_future_ping = 0
        self.spot_pong_received = True
        self.future_pong_received = True

    async def start(self):
        if self.active: return
        self.active = True
        logging.info("[GATE] Starting WebSocket client...")
        await self.fetch_symbols()
        asyncio.create_task(self._maintain_connections())

    async def stop(self):
        self.active = False
        if self.spot_ws:
            await self.spot_ws.close()
            self.spot_ws = None
        if self.future_ws:
            await self.future_ws.close()
            self.future_ws = None
        logging.info("[GATE] WebSocket client stopped.")

    async def fetch_symbols(self):
        """Fetch active USDT symbols from Gate API"""
        spot_syms = set()
        future_syms = set()
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                # 1. Fetch Future pairs
                async with session.get("https://api.gateio.ws/api/v4/futures/usdt/contracts") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            name = item.get("name", "")
                            if name.endswith("_USDT"):
                                std_sym = name.replace("_", "")
                                future_syms.add(std_sym)
                                
                                # 解析资金费率静态规则 (初始打底)
                                try:
                                    f_interval = int(item.get("funding_interval", 28800)) // 3600
                                    f_limit = float(item.get("funding_rate_limit", 0))
                                    self.price_book.update({
                                        "symbol": std_sym,
                                        "exchange": "gate_linear",
                                        "fundingInterval": f_interval,
                                        "fundingMax": f_limit,
                                        "fundingMin": -f_limit
                                    })
                                except:
                                    pass
                                
                # 2. Fetch Spot pairs
                async with session.get("https://api.gateio.ws/api/v4/spot/currency_pairs") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            id_str = item.get("id", "")
                            if id_str.endswith("_USDT"):
                                spot_syms.add(id_str.replace("_", ""))
                                
            self.spot_symbols = spot_syms
            self.future_symbols = future_syms
            self.symbols = spot_syms.union(future_syms)
            logging.info(f"[GATE] Fetched {len(self.symbols)} USDT symbols (Spot: {len(spot_syms)}, Future: {len(future_syms)}) from API.")
        except Exception as e:
            logging.error(f"[GATE] Failed to fetch symbols: {e}")

    def subscribe(self, symbols: list):
        """外部调用以动态订阅关注的币对"""
        new_spot = []
        new_future = []
        for sym in symbols:
            s = sym.replace('/', '')
            if s not in self.symbols:
                self.symbols.add(s)
                self.spot_symbols.add(s)
                self.future_symbols.add(s)
                new_spot.append(s)
                new_future.append(s)
        
        if new_spot and self.spot_ws:
            asyncio.create_task(self._subscribe_spot(new_spot))
        if new_future and self.future_ws:
            asyncio.create_task(self._subscribe_future(new_future))

    async def _maintain_connections(self):
        while self.active:
            if not self.spot_ws or self.spot_ws.closed:
                asyncio.create_task(self._connect_spot())
            if not self.future_ws or self.future_ws.closed:
                asyncio.create_task(self._connect_future())
            await asyncio.sleep(5)

    def _get_gate_symbol(self, sym: str) -> str:
        """从 Binance 符号转为 Gate 要求的下划线系统（例如 HYPEUSDT -> HYPE_USDT）"""
        if sym.endswith("USDT") and "_" not in sym:
            return f"{sym[:-4]}_USDT"
        return sym

    def _get_std_symbol(self, gate_sym: str) -> str:
        """从 Gate 返回格式 HYPE_USDT 转回系统标准 HYPEUSDT"""
        return gate_sym.replace("_", "")

    # ── Spot WebSocket ────────────────────────────────────────────────────────
    
    async def _connect_spot(self):
        try:
            self.spot_ws = await websockets.connect(GATE_SPOT_WS)
            logging.info("[GATE SPOT] Connected to WebSocket")
            self.last_spot_ping = time.time()
            self.spot_pong_received = True
            
            if self.spot_symbols:
                await self._subscribe_spot(list(self.spot_symbols))
                
            asyncio.create_task(self._listen_spot())
            asyncio.create_task(self._ping_spot())
        except Exception as e:
            logging.error(f"[GATE SPOT] Connection failed: {e}")
            await asyncio.sleep(5)

    async def _subscribe_spot(self, symbols: list):
        if not self.spot_ws: return
        try:
            gate_syms = [self._get_gate_symbol(s) for s in symbols]
            chunk_size = 100
            for i in range(0, len(gate_syms), chunk_size):
                chunk = gate_syms[i:i+chunk_size]
                sub_msg = {
                    "time": int(time.time()),
                    "channel": "spot.book_ticker",
                    "event": "subscribe",
                    "payload": chunk
                }
                await self.spot_ws.send(json.dumps(sub_msg))
                
                # Subscribe to spot tickers for real 24H volume & last price
                ticker_msg = {
                    "time": int(time.time()),
                    "channel": "spot.tickers",
                    "event": "subscribe",
                    "payload": chunk
                }
                await self.spot_ws.send(json.dumps(ticker_msg))
                
                await asyncio.sleep(0.1)
            logging.info(f"[GATE SPOT] Subscribed to {len(symbols)} pairs")
        except Exception as e:
            logging.error(f"[GATE SPOT] Subscribe error: {e}")

    async def _ping_spot(self):
        while self.active and self.spot_ws and not self.spot_ws.closed:
            try:
                if not self.spot_pong_received and time.time() - self.last_spot_ping > self.ping_interval * 2:
                    logging.warning("[GATE SPOT] Ping timeout! Reconnecting...")
                    await self.spot_ws.close()
                    break
                
                if time.time() - self.last_spot_ping >= self.ping_interval:
                    ping_msg = {
                        "time": int(time.time()),
                        "channel": "spot.ping",
                        "event": "ping",
                        "payload": []
                    }
                    self.spot_pong_received = False
                    await self.spot_ws.send(json.dumps(ping_msg))
                    self.last_spot_ping = time.time()
                
                await asyncio.sleep(5)
            except Exception:
                break

    async def _listen_spot(self):
        try:
            while self.active and self.spot_ws:
                msg = await self.spot_ws.recv()
                data = json.loads(msg)
                
                event = data.get("event")
                channel = data.get("channel")

                if event == "pong":
                    self.spot_pong_received = True
                    continue
                
                if channel == "spot.book_ticker" and event == "update":
                    payload = data.get("result", {})
                    # payload 可能是单个对象
                    if isinstance(payload, dict):
                        gate_sym = payload.get("s")
                        std_sym = self._get_std_symbol(gate_sym)
                        
                        bid = float(payload.get("b", 0))
                        ask = float(payload.get("a", 0))
                        if bid > 0 and ask > 0:
                            if std_sym == "BTCUSDT":
                                logging.info(f"[GATE DBG SPOT] Ticker: {std_sym} bid={bid} ask={ask}")
                            self.price_book.update({
                                "symbol": std_sym,
                                "exchange": "gate_spot",
                                "bid": bid,
                                "ask": ask,
                                "update_time": time.time()
                            })
                            
                elif channel == "spot.tickers" and event == "update":
                    payload = data.get("result", {})
                    if not isinstance(payload, list):
                        payload = [payload]
                        
                    for t in payload:
                        gate_sym = t.get("currency_pair")
                        if not gate_sym: continue
                        std_sym = self._get_std_symbol(gate_sym)
                        
                        last_price = float(t.get("last", 0))
                        quote_vol = float(t.get("quote_volume", 0))
                        
                        self.price_book.update({
                            "symbol": std_sym,
                            "exchange": "gate_spot",
                            "lastPrice": last_price,
                            "volume": quote_vol
                        })

        except websockets.exceptions.ConnectionClosed:
            logging.warning("[GATE SPOT] WebSocket closed")
        except Exception as e:
            logging.error(f"[GATE SPOT] Error reading stream: {e}")

    # ── Future WebSocket ──────────────────────────────────────────────────────

    async def _connect_future(self):
        try:
            self.future_ws = await websockets.connect(GATE_FUTURE_WS)
            logging.info("[GATE FUTURE] Connected to WebSocket")
            self.last_future_ping = time.time()
            self.future_pong_received = True
            
            if self.future_symbols:
                await self._subscribe_future(list(self.future_symbols))
                
            asyncio.create_task(self._listen_future())
            asyncio.create_task(self._ping_future())
        except Exception as e:
            logging.error(f"[GATE FUTURE] Connection failed: {e}")
            await asyncio.sleep(5)

    async def _subscribe_future(self, symbols: list):
        if not self.future_ws: return
        try:
            gate_syms = [self._get_gate_symbol(s) for s in symbols]
            chunk_size = 100
            
            for i in range(0, len(gate_syms), chunk_size):
                chunk = gate_syms[i:i+chunk_size]
                
                # Subscribe to Order Book Ticker
                ticker_msg = {
                    "time": int(time.time()),
                    "channel": "futures.book_ticker",
                    "event": "subscribe",
                    "payload": chunk
                }
                await self.future_ws.send(json.dumps(ticker_msg))
                
                # Subscribe to Tickers (for Funding rate & Index Price)
                funding_msg = {
                    "time": int(time.time()),
                    "channel": "futures.tickers",
                    "event": "subscribe",
                    "payload": chunk
                }
                await self.future_ws.send(json.dumps(funding_msg))
                await asyncio.sleep(0.1)
            
            logging.info(f"[GATE FUTURE] Subscribed to {len(symbols)} pairs")
        except Exception as e:
            logging.error(f"[GATE FUTURE] Subscribe error: {e}")

    async def _ping_future(self):
        while self.active and self.future_ws and not self.future_ws.closed:
            try:
                if not self.future_pong_received and time.time() - self.last_future_ping > self.ping_interval * 2:
                    logging.warning("[GATE FUTURE] Ping timeout! Reconnecting...")
                    await self.future_ws.close()
                    break
                
                if time.time() - self.last_future_ping >= self.ping_interval:
                    ping_msg = {
                        "time": int(time.time()),
                        "channel": "futures.ping",
                        "event": "ping",
                        "payload": []
                    }
                    self.future_pong_received = False
                    await self.future_ws.send(json.dumps(ping_msg))
                    self.last_future_ping = time.time()
                
                await asyncio.sleep(5)
            except Exception:
                break

    async def _listen_future(self):
        try:
            while self.active and self.future_ws:
                msg = await self.future_ws.recv()
                data = json.loads(msg)
                
                event = data.get("event")
                channel = data.get("channel")

                if event == "pong":
                    self.future_pong_received = True
                    continue
                
                if channel == "futures.book_ticker" and event == "update":
                    payload = data.get("result", {})
                    if not isinstance(payload, list):
                        payload = [payload]
                    for item in payload:
                        if not isinstance(item, dict): continue
                        gate_sym = item.get("s")
                        if not gate_sym: gate_sym = item.get("contract")
                        if not gate_sym: continue
                        
                        std_sym = self._get_std_symbol(gate_sym)
                        
                        bid = float(item.get("b", 0))
                        ask = float(item.get("a", 0))
                        
                        if bid > 0 and ask > 0:
                            if std_sym == "BTCUSDT":
                                logging.info(f"[GATE DBG FUT] Ticker: {std_sym} bid={bid} ask={ask}")
                            # Update only bid/ask, preserve existing funding info
                            self.price_book.update({
                                "symbol": std_sym,
                                "exchange": "gate_linear",
                                "bid": bid,
                                "ask": ask,
                                "update_time": time.time()
                            })
                            
                elif channel == "futures.tickers" and event == "update":
                    payload = data.get("result", [])
                    if not isinstance(payload, list):
                        payload = [payload]
                        
                    for t in payload:
                        gate_sym = t.get("contract")
                        std_sym = self._get_std_symbol(gate_sym)
                        
                        funding_rate = float(t.get("funding_rate", 0))
                        index_price = float(t.get("index_price", 0))
                        mark_price = float(t.get("mark_price", 0))
                        last_price = float(t.get("last", 0))
                        vol = float(t.get("volume_24h_quote", 0))
                        
                        self.price_book.update({
                            "symbol": std_sym,
                            "exchange": "gate_linear",
                            "fundingRate": funding_rate,
                            "indexPrice": index_price,
                            "markPrice": mark_price,
                            "lastPrice": last_price,
                            "volume": vol
                        })
                        
        except websockets.exceptions.ConnectionClosed:
            logging.warning("[GATE FUTURE] WebSocket closed")
        except Exception as e:
            logging.error(f"[GATE FUTURE] Error reading stream: {e}")
