import asyncio
import json
import logging
import time
import secrets
import aiohttp
import websockets
from eth_account import Account
from eth_account.messages import encode_typed_data

class NadoClient:
    """
    Nado DEX 原生驱动器 (无 CCXT)，使用以太坊私钥 + EIP-712 签名直连 Sequencer。
    """
    REST_URL = "https://gateway.prod.nado.xyz/v1"
    WS_URL = "wss://gateway.prod.nado.xyz/v1/subscribe"
    ARCHIVE_URL = "https://archive.prod.nado.xyz/v2"
    CHAIN_ID = 57073
    ENDPOINT_ADDR = ""

    def __init__(self, private_key: str, subaccount_name: str = "default"):
        self.private_key = private_key
        if private_key:
            self.account = Account.from_key(private_key)
            self.address = self.account.address
        else:
            self.account = None
            self.address = "0x" + "0" * 40

        self.subaccount_name = subaccount_name
        self.session = None
        self._ws = None
        self.price_book = {}

        # product_id -> {"type": "spot"|"linear", "symbol": "BTCUSDT", "raw": "BTC-PERP", ...}
        self.products = {}
        # "BTCUSDT_linear" -> product_id
        self.symbol_to_id = {}
        # 精度
        self.market_info = {}
        self.volumes = {}  # key -> quote_volume (USDT 24h)
        self.oracle_prices = {}  # key -> oracle_price (index price)

        self.last_ping_time = 0
        self._ticker_callback = None

    def set_ticker_callback(self, cb):
        self._ticker_callback = cb

    async def _emit_ticker(self, key: str, bid: float, ask: float, funding_rate: float = 0.0):
        info = None
        for pid, p in self.products.items():
            if p["key"] == key:
                info = p
                break
        if not info:
            return
        exchange_name = f"nado_{info['type']}"
        mark_price = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
        ticker = {
            "symbol": info["symbol"],
            "exchange": exchange_name,
            "bid": bid,
            "ask": ask,
            "fundingRate": funding_rate,
            "fundingInterval": 1,
            "volume": self.volumes.get(key, 0),
            "indexPrice": self.oracle_prices.get(key, 0),
            "markPrice": mark_price,
        }
        if self._ticker_callback:
            await self._ticker_callback(ticker)

    async def init(self):
        self.session = aiohttp.ClientSession()
        await self._load_contracts()
        await self.load_markets()
        await self._fetch_volumes()
        await self._fetch_oracle_prices()
        await self._fetch_initial_prices()

    async def close(self):
        if self.session:
            await self.session.close()
        if self._ws:
            await self._ws.close()

    async def _post_query(self, type_name: str, payload: dict = None):
        if not payload:
            payload = {}
        payload["type"] = type_name
        async with self.session.post(f"{self.REST_URL}/query", json=payload) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("data")
            raise Exception(f"Nado query [{type_name}] error: {data}")

    async def _load_contracts(self):
        data = await self._post_query("contracts")
        self.CHAIN_ID = int(data.get("chain_id", self.CHAIN_ID))
        self.ENDPOINT_ADDR = data.get("endpoint_addr", self.ENDPOINT_ADDR)

    async def load_markets(self):
        data = await self._post_query("symbols")
        symbols_map = data.get("symbols", {})
        for raw_sym, info in symbols_map.items():
            pid = info["product_id"]
            sym_type = info.get("type", "perp")

            if sym_type == "spot":
                # BTC-USDT -> BTCUSDT_spot
                norm = raw_sym.replace("-", "")
                key = f"{norm}_spot"
                mtype = "spot"
            else:
                # BTC-PERP -> BTCUSDT_linear
                base = raw_sym.replace("-PERP", "").replace("-", "")
                norm = f"{base}USDT"
                key = f"{norm}_linear"
                mtype = "linear"

            self.symbol_to_id[key] = pid
            self.products[pid] = {"type": mtype, "symbol": norm, "key": key, "raw": raw_sym}

            price_inc = float(info.get("price_increment_x18", 0)) / 1e18
            size_inc = float(info.get("size_increment", 0)) / 1e18
            min_size = float(info.get("min_size", 0)) / 1e18
            maker_fee = float(info.get("maker_fee_rate_x18", 0)) / 1e18
            taker_fee = float(info.get("taker_fee_rate_x18", 0)) / 1e18
            self.market_info[key] = {
                "price_increment": price_inc,
                "size_increment": size_inc,
                "min_size": min_size,
                "maker_fee": maker_fee,
                "taker_fee": taker_fee,
                "trading_status": info.get("trading_status", ""),
            }

        logging.info(f"Nado loaded {len(self.products)} markets")

    async def _fetch_volumes(self):
        try:
            async with self.session.get(f"{self.ARCHIVE_URL}/tickers") as resp:
                data = await resp.json()
            # data 格式: { "BTC-PERP_USDT0": { product_id, quote_volume, ... }, ... }
            pid_to_key = {pid: info["key"] for pid, info in self.products.items()}
            for ticker_id, info in data.items():
                pid = info.get("product_id")
                if pid in pid_to_key:
                    key = pid_to_key[pid]
                    self.volumes[key] = info.get("quote_volume", 0)
            logging.info(f"Nado fetched volumes for {len(self.volumes)} products")
        except Exception as e:
            logging.warning(f"Nado volume fetch failed: {e}")

    async def _fetch_oracle_prices(self):
        try:
            data = await self._post_query("all_products")
            pid_to_key = {pid: info["key"] for pid, info in self.products.items()}
            for p in data.get("perp_products", []):
                pid = p.get("product_id")
                if pid in pid_to_key:
                    oracle = float(p.get("oracle_price_x18", "0")) / 1e18
                    self.oracle_prices[pid_to_key[pid]] = oracle
            for p in data.get("spot_products", []):
                pid = p.get("product_id")
                if pid in pid_to_key:
                    oracle = float(p.get("oracle_price_x18", "0")) / 1e18
                    self.oracle_prices[pid_to_key[pid]] = oracle
            logging.info(f"Nado fetched oracle prices for {len(self.oracle_prices)} products")
        except Exception as e:
            logging.warning(f"Nado oracle price fetch failed: {e}")

    async def _fetch_initial_prices(self):
        tasks = []
        pids = []
        for pid in self.products:
            pids.append(pid)
            tasks.append(self._post_query("market_price", {"product_id": pid}))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for pid, res in zip(pids, results):
            if isinstance(res, Exception):
                continue
            info = self.products[pid]
            key = info["key"]
            bid = float(res.get("bid_x18", "0")) / 1e18
            ask = float(res.get("ask_x18", "0")) / 1e18
            self.price_book[key] = {"bid": bid, "ask": ask, "fundingRate": 0.0}
            await self._emit_ticker(key, bid, ask)
        logging.info(f"Nado fetched initial prices for {len(self.price_book)} products")

    async def fetch_balance(self):
        sender = self.get_sender_bytes32()
        data = await self._post_query("subaccount_info", {"sender": sender})
        return data

    def get_sender_bytes32(self) -> str:
        addr_hex = self.address[2:].lower()
        sub_hex = self.subaccount_name.encode("utf-8").ljust(12, b"\x00").hex()
        return "0x" + addr_hex + sub_hex

    # ── 签名与发单 ──────────────────────────────────
    async def place_order(self, symbol: str, type_a: str, side: str, amount: float, price: float, reduce_only: bool = False):
        if not self.account:
            raise ValueError("Nado: 未配置私钥")

        full_key = f"{symbol}_{type_a}"
        if full_key not in self.symbol_to_id:
            raise ValueError(f"Nado: 未知的交易对 {full_key}")

        product_id = self.symbol_to_id[full_key]
        is_buy = side.lower() == "buy"

        sender = self.get_sender_bytes32()
        price_x18 = int(price * 1e18)
        amount_x18 = int(amount * 1e18)
        if not is_buy:
            amount_x18 = -amount_x18

        expiration = int(time.time()) + 86400
        nonce = ((int(time.time() * 1000) + 60000) << 20) + secrets.randbits(20)

        # appendix: version=1, 默认 cross-margin, 默认 IOC (taker)
        # [7:0]=1 version, [10:9]=1 IOC
        appendix = 1 | (1 << 9)
        if reduce_only:
            appendix |= (1 << 11)

        verifying_contract = "0x" + product_id.to_bytes(20, "big").hex()

        domain = {
            "name": "Nado",
            "version": "0.0.1",
            "chainId": self.CHAIN_ID,
            "verifyingContract": verifying_contract,
        }
        types = {
            "Order": [
                {"name": "sender", "type": "bytes32"},
                {"name": "priceX18", "type": "int128"},
                {"name": "amount", "type": "int128"},
                {"name": "expiration", "type": "uint64"},
                {"name": "nonce", "type": "uint64"},
                {"name": "appendix", "type": "uint128"},
            ]
        }
        message = {
            "sender": bytes.fromhex(sender[2:]),
            "priceX18": price_x18,
            "amount": amount_x18,
            "expiration": expiration,
            "nonce": nonce,
            "appendix": appendix,
        }

        signable = encode_typed_data(
            domain_data=domain,
            message_types=types,
            primary_type="Order",
            message_data=message,
        )
        signed = self.account.sign_message(signable)
        sig_hex = "0x" + signed.signature.hex()

        payload = {
            "place_order": {
                "product_id": product_id,
                "order": {
                    "sender": sender,
                    "priceX18": str(price_x18),
                    "amount": str(amount_x18),
                    "expiration": str(expiration),
                    "nonce": str(nonce),
                    "appendix": str(appendix),
                },
                "signature": sig_hex,
            }
        }

        async with self.session.post(f"{self.REST_URL}/execute", json=payload) as resp:
            res = await resp.json()
            if res.get("status") == "success":
                logging.info(f"Nado order OK: {symbol} {side} {amount}@{price}")
                return res.get("data", res)
            raise Exception(f"Nado place_order fail: {res}")

    # ── WebSocket 行情订阅 ─────────────────────────
    async def run_ws(self):
        while True:
            try:
                async with websockets.connect(
                    self.WS_URL
                ) as ws:
                    self._ws = ws
                    logging.info("Nado WS connected")

                    # 逐产品订阅 best_bid_offer 和 funding_rate
                    sub_id = 1
                    for pid, info in self.products.items():
                        await ws.send(json.dumps({
                            "method": "subscribe",
                            "stream": {"type": "best_bid_offer", "product_id": pid},
                            "id": sub_id,
                        }))
                        sub_id += 1
                        if info["type"] == "linear":
                            await ws.send(json.dumps({
                                "method": "subscribe",
                                "stream": {"type": "funding_rate", "product_id": pid},
                                "id": sub_id,
                            }))
                            sub_id += 1
                    logging.info(f"Nado WS subscribed to {sub_id-1} streams")

                    self.last_ping_time = time.time()
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        await self._handle_ws_msg(data)

                        now = time.time()
                        if now - self.last_ping_time > 20:
                            await ws.ping()
                            self.last_ping_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Nado WS error: {e}")
                await asyncio.sleep(3)

    async def _handle_ws_msg(self, data: dict):
        msg_type = data.get("type")
        if not msg_type:
            return

        if msg_type == "best_bid_offer":
            pid = data.get("product_id")
            if pid not in self.products:
                return
            info = self.products[pid]
            key = info["key"]
            bid = float(data.get("bid_price", "0")) / 1e18
            ask = float(data.get("ask_price", "0")) / 1e18
            if key not in self.price_book:
                self.price_book[key] = {"bid": 0, "ask": 0, "fundingRate": 0.0}
            self.price_book[key]["bid"] = bid
            self.price_book[key]["ask"] = ask
            await self._emit_ticker(key, bid, ask, self.price_book[key].get("fundingRate", 0))

        elif msg_type == "funding_rate":
            pid = data.get("product_id")
            if pid not in self.products:
                return
            info = self.products[pid]
            key = info["key"]
            # Nado funding_rate_x18 是 24h 总费率，除以 24 得到每小时费率
            fr = float(data.get("funding_rate_x18", "0")) / 1e18 / 24
            if key not in self.price_book:
                self.price_book[key] = {"bid": 0, "ask": 0, "fundingRate": 0.0}
            self.price_book[key]["fundingRate"] = fr
            pb = self.price_book[key]
            await self._emit_ticker(key, pb["bid"], pb["ask"], fr)
