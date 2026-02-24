"""
Lighter DEX 原生驱动器 (无 CCXT)
REST: https://mainnet.zklighter.elliot.ai
WS:   wss://mainnet.zklighter.elliot.ai/stream
"""
import asyncio
import json
import logging
import aiohttp
import websockets


class LighterClient:
    """
    Lighter DEX 连接器，提供行情订阅和下单功能。
    只有 perp 市场（无 spot）。
    """
    REST_URL = "https://mainnet.zklighter.elliot.ai"
    WS_URL = "wss://mainnet.zklighter.elliot.ai/stream"

    def __init__(self, api_key_index: int = 0, private_key: str = "", account_index: int = 0):
        self.api_key_index = api_key_index
        self.private_key = private_key
        self.account_index = account_index

        self.session = None
        self._ws = None

        # market_id -> { "symbol": "ETHUSDT", "raw": "ETH", "key": "ETHUSDT_linear", ... }
        self.products = {}
        # "ETHUSDT_linear" -> market_id
        self.symbol_to_id = {}
        self.market_info = {}
        self.price_book = {}

        self._ticker_callback = None

    def set_ticker_callback(self, cb):
        self._ticker_callback = cb

    async def _emit_ticker(self, key: str, bid: float, ask: float,
                           funding_rate: float = 0.0, index_price: float = 0.0,
                           mark_price: float = 0.0, volume: float = 0.0):
        info = None
        for mid, p in self.products.items():
            if p["key"] == key:
                info = p
                break
        if not info:
            return
        ticker = {
            "symbol": info["symbol"],
            "exchange": "lighter_linear",
            "bid": bid,
            "ask": ask,
            "fundingRate": funding_rate,
            "fundingInterval": 1,
            "volume": volume,
            "indexPrice": index_price,
            "markPrice": mark_price,
        }
        if self._ticker_callback:
            await self._ticker_callback(ticker)

    async def init(self):
        self.session = aiohttp.ClientSession()
        await self._load_markets()
        logging.info(f"[Lighter] Init OK, {len(self.products)} markets loaded")

    async def close(self):
        if self.session:
            await self.session.close()
        if self._ws:
            await self._ws.close()

    async def _load_markets(self):
        async with self.session.get(f"{self.REST_URL}/api/v1/orderBookDetails") as resp:
            data = await resp.json()

        for m in data.get("order_book_details", []):
            if m.get("status") != "active":
                continue
            if m.get("market_type") != "perp":
                continue

            mid = m["market_id"]
            raw_sym = m["symbol"]

            # 跳过外汇/商品品种（包含 USD/XAU/XAG 等）
            if "USD" in raw_sym or raw_sym in ("XAU", "XAG", "XPT", "XPD"):
                continue

            # 标准化: ETH -> ETHUSDT
            norm = f"{raw_sym}USDT"
            key = f"{norm}_linear"

            self.products[mid] = {
                "symbol": norm,
                "raw": raw_sym,
                "key": key,
                "market_id": mid,
            }
            self.symbol_to_id[key] = mid
            self.market_info[key] = {
                "price_decimals": m.get("price_decimals", 2),
                "size_decimals": m.get("size_decimals", 0),
                "min_base_amount": m.get("min_base_amount", "0"),
                "maker_fee": m.get("maker_fee", "0"),
                "taker_fee": m.get("taker_fee", "0"),
            }

            # 用 REST 数据初始化 price_book（last_trade_price 作为初始 bid/ask）
            ltp = float(m.get("last_trade_price", 0))
            vol = float(m.get("daily_quote_token_volume", 0))
            if ltp > 0:
                self.price_book[key] = {
                    "bid": ltp, "ask": ltp,
                    "fundingRate": 0.0,
                    "indexPrice": 0, "markPrice": 0,
                    "volume": vol,
                }
                await self._emit_ticker(key, ltp, ltp, volume=vol)

        logging.info(f"[Lighter] Loaded {len(self.products)} crypto perp markets")

    async def run_ws(self):
        while True:
            try:
                async with websockets.connect(
                    f"{self.WS_URL}?readonly=true",
                    extra_headers={"Sec-WebSocket-Extensions": "permessage-deflate"},
                ) as ws:
                    self._ws = ws
                    logging.info("[Lighter] WS Connected")

                    # 订阅所有市场的 BBO
                    for mid in self.products:
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "channel": f"ticker/{mid}",
                        }))

                    # 订阅所有市场的 market_stats（含 funding / index / volume）
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "channel": "market_stats/all",
                    }))

                    logging.info(f"[Lighter] Subscribed to {len(self.products)} tickers + market_stats/all")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        await self._handle_ws_msg(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Lighter] WS error: {e}")
                await asyncio.sleep(3)

    async def _handle_ws_msg(self, data: dict):
        msg_type = data.get("type", "")

        if msg_type == "update/ticker":
            # BBO 更新: { channel: "ticker:0", ticker: { s: "ETH", a: {price, size}, b: {price, size} } }
            channel = data.get("channel", "")
            parts = channel.split(":")
            if len(parts) != 2:
                return
            try:
                mid = int(parts[1])
            except ValueError:
                return
            if mid not in self.products:
                return

            info = self.products[mid]
            key = info["key"]
            ticker = data.get("ticker", {})
            bid = float(ticker.get("b", {}).get("price", 0))
            ask = float(ticker.get("a", {}).get("price", 0))

            if bid <= 0 or ask <= 0:
                return

            pb = self.price_book.get(key, {})
            pb["bid"] = bid
            pb["ask"] = ask
            self.price_book[key] = pb

            await self._emit_ticker(
                key, bid, ask,
                funding_rate=pb.get("fundingRate", 0),
                index_price=pb.get("indexPrice", 0),
                mark_price=pb.get("markPrice", 0),
                volume=pb.get("volume", 0),
            )

        elif msg_type == "update/market_stats":
            # market_stats/all: { market_stats: { "0": {...}, "92": {...}, ... } }
            stats_map = data.get("market_stats", {})
            for mid_str, stats in stats_map.items():
                try:
                    mid = int(mid_str)
                except ValueError:
                    continue
                if mid not in self.products:
                    continue

                info = self.products[mid]
                key = info["key"]

                idx_price = float(stats.get("index_price", 0))
                mk_price = float(stats.get("mark_price", 0))
                # current_funding_rate 是百分比字符串（如 "-0.0015" → -0.0015%）
                fr_str = stats.get("current_funding_rate", "0")
                fr = float(fr_str) / 100  # 转小数
                vol = float(stats.get("daily_quote_token_volume", 0))

                pb = self.price_book.get(key, {"bid": 0, "ask": 0})
                pb["fundingRate"] = fr
                pb["indexPrice"] = idx_price
                pb["markPrice"] = mk_price
                pb["volume"] = vol
                self.price_book[key] = pb

                if pb["bid"] > 0 and pb["ask"] > 0:
                    await self._emit_ticker(
                        key, pb["bid"], pb["ask"],
                        funding_rate=fr,
                        index_price=idx_price,
                        mark_price=mk_price,
                        volume=vol,
                    )

    async def place_order(self, symbol: str, type_a: str, side: str,
                          amount: float, price: float, reduce_only: bool = False):
        """下单（需要 lighter-sdk，后续实现）"""
        raise NotImplementedError("Lighter place_order 需要配置 lighter-sdk 和 API Key")
