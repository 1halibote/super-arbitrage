"""
交易所连接 + 下单引擎
从旧 executor.py 原样提取底层 CCXT/PAPI 交互代码
"""
import asyncio
import logging
import time
import traceback
import ccxt.async_support as ccxt
from typing import Dict, List, Optional, Union, Tuple

from .key_store import api_key_store
from .models import TradingCard, OrderResult, ExecutionResult, ExecutionStatus


# PAPI URL 修复 Wrapper
class BinancePapiWrapper(ccxt.binance):
    async def request(self, path, api=None, method='GET', params={}, headers=None, body=None, config={}):
        if api == 'papi':
            if 'api' not in self.urls: self.urls['api'] = {}
            if 'papi' not in self.urls['api']:
                self.urls['api']['papi'] = 'https://papi.binance.com/papi/v1'
            if headers is None: headers = {}
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        return await super().request(path, api, method, params, headers, body, config)


class ExchangeClient:
    """交易所连接管理 + 下单"""

    def __init__(self):
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._use_binance_papi = True
        self._initialized = False
        self._order_timestamps: list = []
        self._MAX_ORDERS_PER_MIN = 1000
        self._leverage_cache: Dict[str, int] = {}
        self._price_book = None
        self._nado_client = None

    def set_price_book(self, price_book):
        self._price_book = price_book

    def get_client(self, key: str) -> Optional[ccxt.Exchange]:
        if key.startswith("nado"):
            return self._nado_client
        return self._exchanges.get(key)

    # ── 初始化 ──────────────────────────────────────────

    async def initialize(self):
        if self._initialized: return
        self._initialized = True

        exchanges = api_key_store.list_exchanges()
        for exchange_name in exchanges:
            keys = api_key_store.get_key(exchange_name)
            if not keys: continue

            api_key = keys["api_key"]
            api_secret = keys["api_secret"]
            passphrase = keys.get("passphrase", "")

            try:
                if exchange_name == "binance":
                    self._exchanges["binance_spot"] = ccxt.binance({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'spot', 'fetchMarkets': ['spot']}
                    })
                    self._exchanges["binance_linear"] = ccxt.binanceusdm({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'future'}
                    })
                    self._exchanges["binance_papi"] = BinancePapiWrapper({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'papi'}
                    })
                    logging.info("Initialized Binance Spot & Linear & PAPI")
                    asyncio.create_task(self._detect_binance_pm())

                elif exchange_name == "bybit":
                    self._exchanges["bybit_spot"] = ccxt.bybit({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'spot', 'fetchMarkets': ['spot'], 'recvWindow': 20000}
                    })
                    self._exchanges["bybit_linear"] = ccxt.bybit({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'linear', 'recvWindow': 20000}
                    })
                    logging.info("Initialized Bybit Spot & Linear")

                elif exchange_name == "bitget":
                    self._exchanges["bitget_spot"] = ccxt.bitget({
                        'apiKey': api_key, 'secret': api_secret, 'password': passphrase,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'spot'}
                    })
                    self._exchanges["bitget_linear"] = ccxt.bitget({
                        'apiKey': api_key, 'secret': api_secret, 'password': passphrase,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'swap'}
                    })
                    logging.info("Initialized Bitget Spot & Linear")
                elif exchange_name == "gate":
                    self._exchanges["gate_spot"] = ccxt.gate({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'spot', 'createMarketBuyOrderRequiresPrice': False}
                    })
                    self._exchanges["gate_linear"] = ccxt.gate({
                        'apiKey': api_key, 'secret': api_secret,
                        'enableRateLimit': False,
                        'options': {'defaultType': 'swap'}
                    })
                    logging.info("Initialized Gate Spot & Linear")
                elif exchange_name == "nado":
                    from backend.connectors.nado import NadoClient
                    self._nado_client = NadoClient(api_key, api_secret or "default")
                    await self._nado_client.init()
                    logging.info("Initialized Nado DEX Client")

            except Exception as e:
                logging.error(f"Failed to init CCXT for {exchange_name}: {e}")

        await self._load_markets()
        logging.info(f"ExchangeClient initialized ({len(self._exchanges)} instances)")

    async def _load_markets(self):
        tasks, names = [], []
        for name, ex in self._exchanges.items():
            names.append(name)
            tasks.append(ex.load_markets())
        if not tasks: return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                logging.warning(f"Failed to load markets for {name}: {res}")
            else:
                logging.info(f"Loaded markets for {name}")

    async def _detect_binance_pm(self):
        if "binance_papi" in self._exchanges:
            try:
                client = self._exchanges["binance_papi"]
                await client.load_markets()
                await client.fetch_balance()
                self._use_binance_papi = True
                logging.info(">>> DETECTED: BINANCE PORTFOLIO MARGIN ACCOUNT <<<")
            except Exception as e:
                logging.info(f"Binance PM Check: Failed ({e}). Using Standard FAPI.")
                self._use_binance_papi = False

    async def add_exchange(self, exchange: str, api_key: str, api_secret: str, passphrase: str = "") -> bool:
        api_key_store.set_key(exchange, api_key, api_secret, passphrase)
        
        try:
            if exchange == "binance":
                self._exchanges["binance_spot"] = ccxt.binance({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True, 'options': {'defaultType': 'spot'}
                })
                self._exchanges["binance_linear"] = ccxt.binanceusdm({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True, 'options': {'defaultType': 'future'}
                })
                self._exchanges["binance_papi"] = BinancePapiWrapper({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True, 'options': {'defaultType': 'papi'}
                })
            elif exchange == "bybit":
                self._exchanges["bybit_spot"] = ccxt.bybit({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot',
                        'recvWindow': 20000,
                        'createMarketBuyOrderRequiresPrice': False,
                        'accountType': 'UNIFIED',
                    }
                })
                self._exchanges["bybit_linear"] = ccxt.bybit({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'linear', 'recvWindow': 20000}
                })
            elif exchange == "bitget":
                self._exchanges["bitget_spot"] = ccxt.bitget({
                    'apiKey': api_key, 'secret': api_secret, 'password': passphrase,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                self._exchanges["bitget_linear"] = ccxt.bitget({
                    'apiKey': api_key, 'secret': api_secret, 'password': passphrase,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'swap'}
                })
            elif exchange == "gate":
                self._exchanges["gate_spot"] = ccxt.gate({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot', 'createMarketBuyOrderRequiresPrice': False}
                })
                self._exchanges["gate_linear"] = ccxt.gate({
                    'apiKey': api_key, 'secret': api_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'swap'}
                })
            elif exchange == "nado":
                from backend.connectors.nado import NadoClient
                self._nado_client = NadoClient(api_key, api_secret or "default")
                await self._nado_client.init()
                logging.info("Added Nado DEX")
                return True
            async def _bg_load():
                for k in list(self._exchanges.keys()):
                    if k.startswith(exchange):
                        try: await self._exchanges[k].load_markets()
                        except Exception as e: logging.warning(f"Background load_markets for {k}: {e}")
            asyncio.create_task(_bg_load())
            return True
        except Exception as e:
            logging.error(f"Add exchange failed: {e}")
            return False

    async def remove_exchange(self, exchange: str):
        api_key_store.delete_key(exchange)
        keys_to_remove = [k for k in self._exchanges if k.startswith(exchange)]
        for k in keys_to_remove:
            if k in self._exchanges:
                client = self._exchanges.pop(k)
                await client.close()

    async def shutdown(self):
        for client in self._exchanges.values():
            try: await client.close()
            except: pass

    # ── Symbol 转换 ─────────────────────────────────────

    def _resolve_symbol(self, client, raw_symbol: str, market_type: str) -> str:
        if '/' in raw_symbol:
            return raw_symbol
        try:
            m = client.market(raw_symbol)
            if market_type == 'linear' and m.get('type') in ('spot',):
                raise KeyError('type mismatch')
            return m['symbol']
        except (KeyError, Exception):
            if raw_symbol.endswith('USDT'):
                base = raw_symbol[:-4]
                return f"{base}/USDT" if market_type == 'spot' else f"{base}/USDT:USDT"
        return raw_symbol

    # ── 下单 ────────────────────────────────────────────

    async def _check_rate_limit(self):
        now = time.time()
        self._order_timestamps = [t for t in self._order_timestamps if now - t < 60]
        if len(self._order_timestamps) >= self._MAX_ORDERS_PER_MIN:
            wait = 60 - (now - self._order_timestamps[0])
            if wait > 0:
                logging.warning(f"[RATE] 达到 {self._MAX_ORDERS_PER_MIN}/min 限制，等待 {wait:.1f}s")
                await asyncio.sleep(wait)
        self._order_timestamps.append(time.time())

    async def _create_order(self, client: ccxt.Exchange, exchange_name: str,
                            symbol: str, side: str, amount: float, params: Dict) -> Dict:
        await self._check_rate_limit()

        async def _execute_papi_order(c, s, side_str, amt, p):
            try:
                if not c.markets: await c.load_markets()
                unified_symbol = s
                try:
                    market = c.market(s)
                except (KeyError, Exception):
                    if s.endswith('USDT') and '/' not in s:
                        base = s[:-4]
                        unified_symbol = f"{base}/USDT:USDT"
                    logging.info(f"[PAPI] Symbol '{s}' -> Unified '{unified_symbol}'")
                    market = c.market(unified_symbol)

                amt = float(c.amount_to_precision(unified_symbol, amt))
                min_amt = market.get('limits', {}).get('amount', {}).get('min', 0)
                if amt <= 0 or (min_amt and amt < min_amt):
                    logging.error(f"[PAPI SKIP] Amount {amt} < min {min_amt}")
                    return

                req = {
                    'symbol': market['id'],
                    'side': side_str.upper(),
                    'type': 'MARKET',
                    'quantity': c.amount_to_precision(unified_symbol, amt),
                    'newOrderRespType': 'RESULT' # 极其重要：否则默认 ACK 会导致返回没有成交量！
                }
                if 'type' in p: req['type'] = p['type'].upper()
                if 'price' in p: req['price'] = c.price_to_precision(unified_symbol, p['price'])
                if 'positionSide' in p: req['positionSide'] = p['positionSide']
                if 'reduceOnly' in p: req['reduceOnly'] = str(p['reduceOnly']).lower()

                if 'papi' not in c.urls.get('api', {}):
                    c.urls.setdefault('api', {})['papi'] = 'https://papi.binance.com/papi/v1'

                logging.info(f"[PAPI EXEC] {req}")
                response = await c.request('um/order', api='papi', method='POST', params=req)
                return c.parse_order(response, market)

            except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as e:
                logging.critical(f"[PAPI RATE LIMIT] {e}")
                await asyncio.sleep(10)
                raise e
            except Exception as e:
                if '429' in str(e) or 'Too many requests' in str(e):
                    logging.critical(f"[PAPI RATE LIMIT] {e}")
                    await asyncio.sleep(10)
                if '-4061' in str(e) and 'positionSide' in p:
                    logging.warning("[PAPI] -4061, retrying without positionSide")
                    req_retry = {
                        'symbol': market['id'], 'side': side_str.upper(),
                        'type': 'MARKET', 'quantity': c.amount_to_precision(unified_symbol, amt),
                    }
                    if 'reduceOnly' in p: req_retry['reduceOnly'] = str(p['reduceOnly']).lower()
                    response = await c.request('um/order', api='papi', method='POST', params=req_retry)
                    return c.parse_order(response, market)
                logging.error(f"[PAPI EXEC CRASH] {e}\n{traceback.format_exc()}")
                raise

        # PAPI 路由
        if "binance" in exchange_name and self._use_binance_papi:
            if client.options.get('defaultType') in ('future', 'linear'):
                papi_client = self._exchanges.get("binance_papi")
                if papi_client:
                    return await _execute_papi_order(papi_client, symbol, side, amount, params)

        if exchange_name == "binance_papi" or client.options.get('defaultType') == 'papi':
            return await _execute_papi_order(client, symbol, side, amount, params)

        try:
            # CCXT 的底层强校验：把为了内部使用的假参数剔除，防止报 'Request parameter error'
            clean_params = {k: v for k, v in params.items() if k not in ('type', 'price')}

            # 在发单前用市场最小量兜底，防止 CCXT 内部二次精度截断把量变成 0
            try:
                market_info = client.market(symbol)
                min_amount = market_info.get('limits', {}).get('amount', {}).get('min') or 0
                if min_amount and 0 < amount < min_amount:
                    logging.warning(f"[PRE-ORDER] {client.id} {symbol} amount={amount:.6f} < min={min_amount}, bumping up")
                    amount = float(min_amount)
            except Exception:
                pass

            if side == "buy":
                return await client.create_market_buy_order(symbol, amount, clean_params)
            else:
                return await client.create_market_sell_order(symbol, amount, clean_params)

        except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as e:
            logging.critical(f"[CCXT RATE LIMIT] {e}")
            await asyncio.sleep(10)
            raise e
        except Exception as e:
            if '429' in str(e) or 'Too many requests' in str(e):
                logging.critical(f"[CCXT RATE LIMIT] {e}")
                await asyncio.sleep(10)
                raise e
            if "binance" in exchange_name and "-4061" in str(e) and 'positionSide' in params:
                logging.warning("[CCXT] -4061, retrying without positionSide")
                params_retry = {k: v for k, v in params.items() if k != 'positionSide'}
                if side == "buy":
                    return await client.create_market_buy_order(symbol, amount, params_retry)
                else:
                    return await client.create_market_sell_order(symbol, amount, params_retry)
            raise e

    # ── 套利下单 ────────────────────────────────────────

    async def execute_arbitrage(
        self, card: TradingCard, qty_usdt: float,
        side_a: str, side_b: str,
        is_close: bool = False,
        price_a: float = None, price_b: float = None,
        position_side_a: str = None, position_side_b: str = None
    ) -> ExecutionResult:
        symbol = card.symbol
        exchange_a = card.exchange_a
        exchange_b = card.exchange_b
        leverage = card.leverage
        card_type = card.type

        # 平仓时检查是否有仓位
        skip_a, skip_b = False, False
        if is_close:
            if (card.position_qty_a or 0) <= 0.0001:
                skip_a = True
                logging.warning(f"[EXEC] Skip Leg A Close: position zero")
            if (card.position_qty_b or 0) <= 0.0001:
                skip_b = True
                logging.warning(f"[EXEC] Skip Leg B Close: position zero")
            if skip_a and skip_b:
                return ExecutionResult(status=ExecutionStatus.SUCCESS, error="Both legs empty")

        type_a = "spot" if card_type == "SF" else "linear"
        type_b = "linear"
        ex_key_a = f"{exchange_a.lower()}_{type_a}"
        ex_key_b = f"{exchange_b.lower()}_{type_b}"

        client_a = self._exchanges.get(ex_key_a)
        client_b = self._exchanges.get(ex_key_b)

        if self._use_binance_papi:
            if exchange_a == 'binance' and card_type != "SF":
                client_a = self._exchanges.get("binance_papi")
            if exchange_b == 'binance':
                client_b = self._exchanges.get("binance_papi")

        if not client_a or not client_b:
            return ExecutionResult(status=ExecutionStatus.FAILED, error=f"Exchange not initialized: {ex_key_a} or {ex_key_b}")

        symbol_a = self._resolve_symbol(client_a, symbol, type_a)
        symbol_b = self._resolve_symbol(client_b, symbol, type_b)

        try:
            t_start = time.perf_counter()

            # 1. 设置杠杆
            if leverage > 1 and not is_close:
                async def set_lev_safe(client, ex_key, sym, lev):
                    if "spot" in ex_key: return
                    lev_int = int(lev)
                    cache_key = f"{ex_key}:{sym}"
                    if self._leverage_cache.get(cache_key) == lev_int: return
                    try:
                        papi_client = self._exchanges.get("binance_papi") if 'binance' in ex_key and self._use_binance_papi else None
                        if papi_client:
                            await papi_client.request('um/leverage', api='papi', method='POST', params={
                                'symbol': sym.replace('/', '').replace(':USDT', ''), 'leverage': lev_int
                            })
                        elif 'bitget' in ex_key:
                            await client.set_leverage(lev_int, sym, params={'marginCoin': 'USDT'})
                        elif 'gate' in ex_key:
                            await client.set_leverage(lev_int, sym, params={'settle': 'usdt'})
                        else:
                            await client.set_leverage(lev_int, sym)
                        self._leverage_cache[cache_key] = lev_int
                    except asyncio.TimeoutError:
                        logging.warning(f"[LEV] TIMEOUT {ex_key} {sym}")
                    except Exception as e:
                        if "110043" in str(e) or "leverage not modified" in str(e):
                            self._leverage_cache[cache_key] = lev_int
                        else:
                            logging.warning(f"[LEV] Failed {ex_key} {sym} {lev}x: {e}")

                await asyncio.gather(
                    set_lev_safe(client_a, ex_key_a, symbol_a, leverage),
                    set_lev_safe(client_b, ex_key_b, symbol_b, leverage),
                    return_exceptions=True
                )

            # 2. 价格
            if not price_a or price_a <= 0:
                ticker_a = await client_a.fetch_ticker(symbol_a)
                price_a = float(ticker_a.get('last', 0) or 0)
            if not price_b or price_b <= 0:
                ticker_b = await client_b.fetch_ticker(symbol_b)
                price_b = float(ticker_b.get('last', 0) or 0)

            if not price_a or not price_b:
                return ExecutionResult(status=ExecutionStatus.FAILED, error=f"Invalid prices A={price_a} B={price_b}")

            # 3. 数量
            avg_price = (price_a + price_b) / 2
            raw_qty = qty_usdt / avg_price

            def get_amt(client, sym, amt):
                try:
                    result = float(client.amount_to_precision(sym, amt))
                    if result <= 0 and amt > 0:
                        # 精度截断后变为 0：说明步长太粗，尝试用市场最小量兜底
                        try:
                            min_amt = client.market(sym).get('limits', {}).get('amount', {}).get('min', 0) or 0
                            if min_amt > 0:
                                logging.warning(f"[PRECISION] {client.id} {sym} amt={amt:.6f} rounded to 0, using market min={min_amt}")
                                return float(min_amt)
                        except Exception:
                            pass
                        return amt  # 最后兜底用原始量
                    return result
                except Exception as e:
                    logging.warning(f"[PRECISION] {client.id} {sym} amount_to_precision ({amt}) failed: {e}. Fallback to raw.")
                    return amt

            # 第一步：直接基于原始币数做 FF/SF 的对齐，不掺杂任何精度修剪
            amount_a = raw_qty
            amount_b = raw_qty

            if not is_close:
                if card_type == "SF":
                    # SF: B 腿（合约）步长更粗，A 腿应以 B 为准。但这需留到 get_amt 后处理。
                    # 放宽限制：现货一般精度更高，只要基于统一资金买入即可，不强求完全相等。
                    pass
                else:
                    # FF: 两个合约取 min 保证完全一致
                    final_qty = min(amount_a, amount_b)
                    amount_a = amount_b = final_qty

            # 第二步：将币数转换为交易所需要的单位（张数），并执行各自的精度修剪
            def convert_and_format(client, ex_key, sym, coin_amt):
                # 如果是 Gate 合约，需转张数
                if 'gate' in ex_key and 'spot' not in ex_key:
                    try:
                        cs = client.market(sym).get('contractSize', 1) or 1
                        contracts = coin_amt / cs
                        return get_amt(client, sym, contracts)
                    except Exception:
                        return get_amt(client, sym, coin_amt)
                
                # 否则直接用币数修剪
                return get_amt(client, sym, coin_amt)

            amount_a = convert_and_format(client_a, ex_key_a, symbol_a, amount_a)
            amount_b = convert_and_format(client_b, ex_key_b, symbol_b, amount_b)


            if is_close:
                # 平仓兜底逻辑：兼顾分批 (batching) 和扫尾防粉尘 (dust sweeping)
                # 原理：只有当剩余真实余额不远远大于这次计划平的 amount (例如不足 1.05 倍) 时，才全部平掉防粉尘
                # 否则，严格遵守上层传进来的分批额度 (amount)
                if not skip_a:
                    if "spot" in ex_key_a:
                        try:
                            # 现货腿：获取真实可用余额
                            base_coin = symbol_a.split('/')[0] if '/' in symbol_a else symbol_a.replace('USDT', '')
                            bal = await client_a.fetch_balance()
                            real_qty = float(bal.get('free', {}).get(base_coin, 0) or 0)
                            if real_qty <= 0:
                                real_qty = float(bal.get('total', {}).get(base_coin, 0) or 0)
                                
                            if real_qty > 0:
                                # 智能放大扫尾: 如果实际余额 <= 要平数量的 1.05 倍，直接拉满
                                actual_close_qty = real_qty if real_qty <= amount_a * 1.05 else amount_a
                                amount_a = get_amt(client_a, symbol_a, actual_close_qty)
                                logging.info(f"[CLOSE SPOT_A] {symbol_a} real={real_qty:.6f}, batch={amount_a}")
                            else:
                                return ExecutionResult(status=ExecutionStatus.FAILED, error=f"[CLOSE SPOT] {symbol_a} balance=0 in exchange")
                        except Exception as e:
                            logging.warning(f"[CLOSE SPOT_A] fetch_balance failed: {e}")
                            amount_a = min(amount_a, card.position_qty_a or amount_a)
                    else:
                        # 合约腿 (FF/SF 的 B腿)：基于内部记账或者真实仓位查底
                        pos_a = card.position_qty_a or 0
                        if pos_a > 0 and pos_a <= amount_a * 1.05:
                            amount_a = get_amt(client_a, symbol_a, pos_a)

                if not skip_b:
                    if "spot" in ex_key_b:
                        try:
                            base_coin = symbol_b.split('/')[0] if '/' in symbol_b else symbol_b.replace('USDT', '')
                            bal = await client_b.fetch_balance()
                            real_qty = float(bal.get('free', {}).get(base_coin, 0) or 0)
                            if real_qty <= 0:
                                real_qty = float(bal.get('total', {}).get(base_coin, 0) or 0)
                                
                            if real_qty > 0:
                                actual_close_qty = real_qty if real_qty <= amount_b * 1.05 else amount_b
                                amount_b = get_amt(client_b, symbol_b, actual_close_qty)
                                logging.info(f"[CLOSE SPOT_B] {symbol_b} real={real_qty:.6f}, batch={amount_b}")
                            else:
                                skip_b = True
                        except Exception as e:
                            logging.warning(f"[CLOSE SPOT_B] fetch_balance failed: {e}")
                            amount_b = min(amount_b, card.position_qty_b or amount_b)
                    else:
                        # 合约腿
                        pos_b = card.position_qty_b or 0
                        if pos_b > 0 and pos_b <= amount_b * 1.05:
                            amount_b = get_amt(client_b, symbol_b, pos_b)


            # 4. 参数
            def to_ccxt_side(s):
                s = s.upper()
                return "buy" if s in ("BUY", "LONG") else "sell"

            s_a, s_b = to_ccxt_side(side_a), to_ccxt_side(side_b)

            params_a = {}
            if "bybit_linear" in ex_key_a:
                idx = 1
                if position_side_a and position_side_a.upper() == "SHORT": idx = 2
                params_a["positionIdx"] = idx
                if is_close: params_a["reduceOnly"] = True
            elif "binance_linear" in ex_key_a or "binance_papi" in ex_key_a:
                params_a["positionSide"] = (position_side_a or "LONG").upper()
            elif "bitget_linear" in ex_key_a:
                params_a["marginCoin"] = "USDT"
                params_a["hedged"] = True
                if is_close: params_a["reduceOnly"] = True
            elif "bitget_spot" in ex_key_a:
                if s_a == "buy": params_a["cost"] = qty_usdt
            elif "gate_spot" in ex_key_a:
                if s_a == "buy": params_a["cost"] = qty_usdt
            elif "gate_linear" in ex_key_a:
                if is_close: params_a["reduceOnly"] = True

            params_b = {}
            if "bybit_linear" in ex_key_b:
                idx = 2
                if position_side_b and position_side_b.upper() == "LONG": idx = 1
                params_b["positionIdx"] = idx
                if is_close: params_b["reduceOnly"] = True
            elif "binance_linear" in ex_key_b or "binance_papi" in ex_key_b:
                params_b["positionSide"] = (position_side_b or "SHORT").upper()
            elif "bitget_linear" in ex_key_b:
                params_b["marginCoin"] = "USDT"
                params_b["hedged"] = True
                if is_close: params_b["reduceOnly"] = True
            elif "bitget_spot" in ex_key_b:
                if s_b == "buy": params_b["cost"] = qty_usdt
            elif "gate_spot" in ex_key_b:
                if s_b == "buy": params_b["cost"] = qty_usdt
            elif "gate_linear" in ex_key_b:
                if is_close: params_b["reduceOnly"] = True

            logging.info(f"[EXEC] {symbol}: {exchange_a}({s_a} {amount_a}) & {exchange_b}({s_b} {amount_b})")

            # 5. 并行下单
            async def _skip(): return None
            task_a = _skip() if skip_a else self._create_order(client_a, exchange_a, symbol_a, s_a, amount_a, params_a)
            task_b = _skip() if skip_b else self._create_order(client_b, exchange_b, symbol_b, s_b, amount_b, params_b)

            t0 = time.perf_counter()
            try:
                res_a, res_b = await asyncio.wait_for(
                    asyncio.gather(task_a, task_b, return_exceptions=True), timeout=8.0
                )
            except asyncio.TimeoutError:
                return ExecutionResult(status=ExecutionStatus.FAILED, error="Order Timeout")

            latency = (time.perf_counter() - t0) * 1000
            logging.info(f"[PERF] Order IO: {latency:.0f}ms")

            err = ""
            success_a = False
            if res_a is None:
                if skip_a:
                    success_a = True
                    res_a = {'id': 'skipped', 'status': 'closed', 'filled': 0, 'price': price_a}
                else:
                    err += "ExA Skipped "
            elif isinstance(res_a, Exception):
                err += f"ExA Error: {res_a} "
            else:
                success_a = True

            success_b = False
            if res_b is None:
                if skip_b:
                    success_b = True
                    res_b = {'id': 'skipped', 'status': 'closed', 'filled': 0, 'price': price_b}
                else:
                    err += "ExB Skipped "
            elif isinstance(res_b, Exception):
                err += f"ExB Error: {res_b} "
            else:
                success_b = True

            order_res_a = OrderResult(
                order_id=str(res_a.get('id', '')), status=res_a.get('status', 'unknown'),
                filled_qty=float(res_a.get('filled', 0) or 0) or amount_a,
                avg_price=float(res_a.get('average', 0) or res_a.get('price', 0) or price_a),
                cost=float(res_a.get('cost', 0) or 0),
                success=True
            ) if success_a else None

            order_res_b = OrderResult(
                order_id=str(res_b.get('id', '')), status=res_b.get('status', 'unknown'),
                filled_qty=float(res_b.get('filled', 0) or 0) or amount_b,
                avg_price=float(res_b.get('average', 0) or res_b.get('price', 0) or price_b),
                cost=float(res_b.get('cost', 0) or 0),
                success=True
            ) if success_b else None


            if err: logging.warning(f"[EXEC] {symbol}: {err}")

            status = ExecutionStatus.SUCCESS
            if not success_a and not success_b: status = ExecutionStatus.FAILED
            elif not success_a or not success_b: status = ExecutionStatus.PARTIAL

            # 原子性保护：开仓时一腿失败，立即市价回滚成功腿，防止单边裸敞口
            if status == ExecutionStatus.PARTIAL and not is_close:
                logging.warning(f"[ATOMIC ROLLBACK] {symbol} partial open, rolling back the successful leg")
                try:
                    if success_a and not success_b:
                        # B 腿失败，回滚 A 腿（发 A 腿反向单）
                        rb_side = "sell" if s_a == "buy" else "buy"
                        rb_amt = float(res_a.get('filled', 0) or amount_a)
                        rb_params = {k: v for k, v in params_a.items()}
                        if "bybit_linear" in ex_key_a or "bitget_linear" in ex_key_a:
                            rb_params["reduceOnly"] = True
                        
                        if "spot" in ex_key_a:
                            if rb_side == "sell" and "cost" in rb_params:
                                del rb_params["cost"]
                            elif rb_side == "buy":
                                rb_params["cost"] = rb_amt * price_a
                                
                        if rb_amt > 0:
                            logging.warning(f"[ATOMIC ROLLBACK] {symbol} rolling back A leg: {rb_side} {rb_amt}")
                            await self._create_order(client_a, exchange_a, symbol_a, rb_side, rb_amt, rb_params)
                    elif success_b and not success_a:
                        # A 腿失败，回滚 B 腿（发 B 腿反向单）
                        rb_side = "sell" if s_b == "buy" else "buy"
                        rb_amt = float(res_b.get('filled', 0) or amount_b)
                        rb_params = {k: v for k, v in params_b.items()}
                        if "bybit_linear" in ex_key_b or "bitget_linear" in ex_key_b:
                            rb_params["reduceOnly"] = True
                        elif "positionSide" in rb_params:
                            pass  # Binance: positionSide 已经正确
                            
                        if "spot" in ex_key_b:
                            if rb_side == "sell" and "cost" in rb_params:
                                del rb_params["cost"]
                            elif rb_side == "buy":
                                rb_params["cost"] = rb_amt * price_b

                        if rb_amt > 0:
                            logging.warning(f"[ATOMIC ROLLBACK] {symbol} rolling back B leg: {rb_side} {rb_amt}")
                            await self._create_order(client_b, exchange_b, symbol_b, rb_side, rb_amt, rb_params)
                except Exception as rb_e:
                    logging.error(f"[ATOMIC ROLLBACK ERROR] {symbol}: {rb_e}")
                    
                # 开仓过程中只要发生单腿失败并进入回滚，其净敞口增加为0，必须将其强行定性为 FAILED 以激活上层熔断和告警
                status = ExecutionStatus.FAILED
                err = "Partial open failed, atomic rollback executed."
                res_a = None
                res_b = None
                # 回滚后标记为失败，内部账本不记账，由后续 sync 校准
                status = ExecutionStatus.FAILED
                order_res_a = None
                order_res_b = None

            return ExecutionResult(status=status, total_latency_ms=latency, error=err,
                                   order_a=order_res_a, order_b=order_res_b)


        except Exception as e:
            logging.error(f"Arbitrage fatal error: {e}\n{traceback.format_exc()}")
            return ExecutionResult(status=ExecutionStatus.FAILED, error=str(e))

    # ── 仓位拉取 ───────────────────────────────────────

    async def fetch_all_positions_map(self, exchange_name: str, is_sf: bool = False) -> Dict:
        client = None
        is_papi = False

        if "binance" in exchange_name:
            if is_sf:
                # 现货腿必须走 spot 账户，PAPI 只覆盖期货
                client = self._exchanges.get("binance_spot")
            elif self._use_binance_papi:
                client = self._exchanges.get("binance_papi")
                is_papi = True
            else:
                client = self._exchanges.get("binance_linear")
        elif "bybit" in exchange_name:
            client = self._exchanges.get("bybit_spot" if is_sf else "bybit_linear")
        elif "bitget" in exchange_name:
            client = self._exchanges.get("bitget_spot" if is_sf else "bitget_linear")
        elif "gate" in exchange_name:
            client = self._exchanges.get("gate_spot" if is_sf else "gate_linear")

        if not client: return {}

        positions_map = {}
        try:
            if is_papi:
                # Binance PM模式：取全局维持保证金率
                acc_res = await client.request('account', api='papi')
                uni_mmr_val = float(acc_res.get('uniMMR', 0))
                global_mr = (1.0 / uni_mmr_val) if uni_mmr_val > 0 else 0.0

                res = await client.request('um/positionRisk', api='papi')
                
                for p in res:
                    p['maintMarginRatio'] = global_mr
                    sym = p.get('symbol')
                    if sym:
                        positions_map.setdefault(sym, []).append({'info': p})
                        if 'USDT' in sym:
                            base = sym.split('USDT')[0]
                            positions_map.setdefault(f"{base}/USDT:USDT", []).append({'info': p})

            elif is_sf or client.options.get('defaultType') == 'spot':
                # 现货账户：查余额，fetch_positions 对现货无效
                bal = await client.fetch_balance()
                for coin, qty in bal.get('total', {}).items():
                    if qty > 0 and coin != 'USDT':
                        slash_sym = f"{coin}/USDT"
                        raw_sym = f"{coin}USDT"
                        entry = {
                            'symbol': slash_sym, 'side': 'long', 'contracts': qty,
                            'info': {'is_spot': True}
                        }
                        positions_map.setdefault(slash_sym, []).append(entry)
                        positions_map.setdefault(raw_sym, []).append(entry)

            elif client.has['fetchPositions']:
                req_params = {}
                if exchange_name == 'gate':
                    req_params['limit'] = 100
                elif exchange_name in ['binance', 'bybit', 'bitget']:
                    req_params['limit'] = 200
                all_pos = await client.fetch_positions(params=req_params)
                
                for p in all_pos:
                    sym = p['symbol']
                    positions_map.setdefault(sym, []).append(p)
                    if p.get('info', {}).get('symbol'):
                        positions_map.setdefault(p['info']['symbol'], []).append(p)

        except Exception as e:
            logging.error(f"[BULK FETCH] Failed for {exchange_name}: {e}")

        return positions_map

    def find_pos_list(self, m: dict, sym: str) -> list:
        # direct match
        if sym in m: return m[sym]
        
        # clean the input target symbol
        target_clean = sym.replace('/', '').replace(':', '').replace('_', '').replace('-', '').upper()
        if target_clean.endswith('USDTUSDT'): 
            target_clean = target_clean[:-4]
            
        # search through keys
        for k, v in m.items():
            k_clean = k.replace('/', '').replace(':', '').replace('_', '').replace('-', '').upper()
            if k_clean.endswith('USDTUSDT'):
                k_clean = k_clean[:-4]
            if k_clean == target_clean:
                return v
                
        return []

    def parse_position_list(self, pos_list: list, sym: str, target_side: str = None):
        """解析仓位列表，返回 (qty, value, avg_price, pnl, liq_price, adl, mmr)"""
        if not pos_list: return 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0

        total_qty, total_val, avg_price, total_pnl = 0.0, 0.0, 0.0, 0.0
        liq_price, adl_val, mmr = 0.0, 0, 0.0
        clean_target = sym.replace('/', '').replace(':USDT', '')

        for p in pos_list:
            p_sym = p.get('symbol', '')
            clean_p = p_sym.replace('/', '').replace(':USDT', '')
            if clean_p and clean_p != clean_target:
                continue

            raw_info = p.get('info', {}) or {}
            raw_side = p.get('side') or raw_info.get('side') or ''
            
            # PAPI/Standard 字段兼容
            amt_keys = ['contracts', 'positionAmt', 'size', 'amount', 'qty']
            amt = 0.0
            for k in amt_keys:
                v = p.get(k) or raw_info.get(k)
                if v is not None:
                    try: amt = float(v); break
                    except: pass

            actual_side = 'unknown'
            ps = (raw_info.get('positionSide') or p.get('positionSide') or '').upper()
            if ps == 'LONG': actual_side = 'long'
            elif ps == 'SHORT': actual_side = 'short'
            elif ps == 'BOTH': # 单向持仓
                if amt > 0: actual_side = 'long'
                elif amt < 0: actual_side = 'short'

            if actual_side == 'unknown' and raw_side:
                if raw_side.lower() in ('short', 'sell'): actual_side = 'short'
                elif raw_side.lower() in ('long', 'buy'): actual_side = 'long'

            if actual_side == 'unknown':
                if amt > 0: actual_side = 'long'
                elif amt < 0: actual_side = 'short'

            # 严格模式：必须匹配 target_side
            if target_side and actual_side != target_side:
                continue

            qty = abs(amt)
            if qty == 0: continue

            # 价格字段增强
            price = 0.0
            price_keys = ['entryPrice', 'avgPrice', 'avgEntryPrice', 'averagePrice']
            for k in price_keys:
                v = p.get(k) or raw_info.get(k)
                if v is not None:
                    try: 
                        p_val = float(v)
                        if p_val > 0: 
                            price = p_val
                            break
                    except: pass

            # 价值字段增强 (去掉 initialMargin)
            notional = 0.0
            notional_keys = ['notional', 'notionalValue', 'positionValue', 'value']
            for k in notional_keys:
                v = p.get(k) or raw_info.get(k)
                if v is not None:
                    try: notional = abs(float(v)); break
                    except: pass

            # Pnl
            upnl = 0.0
            pnl_keys = ['unrealizedPnl', 'unrealisedPnl', 'unRealizedProfit', 'unrealizedProfit', 'unrealizedPL', 'unrealised_pnl', 'up']
            for k in pnl_keys:
                v = p.get(k) or raw_info.get(k)
                if v is not None and v != '':
                    try: upnl = float(v); break
                    except: pass
            # Liq Price, ADL, MMR (增强捕获所有交易所潜在的命名及类型转换)
            liq_raw = p.get('liquidationPrice') or raw_info.get('liquidationPrice') or raw_info.get('liqPrice') or raw_info.get('estimatedLiquidationPrice') or raw_info.get('estLiqPrice')
            if liq_raw not in (None, '', '0', 0):
                try: liq_price = float(liq_raw)
                except ValueError: pass
                
            adl_raw = p.get('adlQuantile') or raw_info.get('adlQuantile') or raw_info.get('adlRankIndicator') or raw_info.get('adl') or raw_info.get('autoDeleverageIndicator')
            if adl_raw not in (None, '', '0', 0):
                try: adl_val = int(float(adl_raw))
                except ValueError: pass
                
            # MMR (维持保证金率) 专项解析
            mmr = 0.0
            ccxt_mmr_pct = p.get('maintenanceMarginPercentage')
            if ccxt_mmr_pct and float(ccxt_mmr_pct) > 0:
                mmr = float(ccxt_mmr_pct) / 100.0
            
            if mmr == 0.0:
                if 'maintenance_rate' in raw_info:  # Gate 是百分制字符串如 "0.45"
                    try: mmr = float(raw_info['maintenance_rate']) / 100.0
                    except: pass
                elif 'positionMM' in raw_info and float(raw_info.get('positionValue', 0)) > 0: # Bybit 直接不给比例只给总额，需手算
                    try: mmr = float(raw_info['positionMM']) / float(raw_info['positionValue'])
                    except: pass
                else:
                    # Binance / Bitget: 直接提供小数比例 (如 0.005)
                    for key in ['maintMarginRatio', 'mmr', 'maintainMarginRate', 'marginRate']:
                        if key in raw_info and raw_info[key] not in (None, '', '0', 0):
                            try: mmr = float(raw_info[key]); break
                            except: pass

            # 价值回退计算
            if notional > 0:
                val = notional
            elif price > 0:
                val = qty * price
            else:
                mark = float(p.get('markPrice') or raw_info.get('markPrice') or 0)
                if mark > 0:
                    val = qty * mark
                    if price == 0: price = mark
                else:
                    val = 0.0

            total_qty += qty
            total_val += val
            total_pnl += upnl
            if price > 0: avg_price = price

        return total_qty, total_val, avg_price, total_pnl, liq_price, adl_val, mmr

    # ── 余额查询 ───────────────────────────────────────

    async def get_balances(self) -> Dict[str, float]:
        aggregated = {}
        for name, client in self._exchanges.items():
            exchange_prefix = name.split('_')[0]
            try:
                bal = await client.fetch_balance()
                usdt = 0
                if 'total' in bal and 'USDT' in bal['total']:
                    usdt = float(bal['total']['USDT'] or 0)
                elif 'USDT' in bal and 'total' in bal['USDT']:
                    usdt = float(bal['USDT']['total'] or 0)

                # Gate 统一账户的 total 是结算中间值（可为负），真正余额在 free
                if exchange_prefix == "gate" and usdt <= 0:
                    free_usdt = float(bal.get('free', {}).get('USDT', 0) or 0)
                    if free_usdt > 0:
                        usdt = free_usdt

                if exchange_prefix == "bybit":
                    aggregated[exchange_prefix] = max(aggregated.get(exchange_prefix, 0), usdt)
                else:
                    aggregated[exchange_prefix] = aggregated.get(exchange_prefix, 0) + usdt
            except Exception:
                pass
        return aggregated

    async def get_assets_details(self) -> Dict[str, dict]:
        results = {}
        from backend.execution.key_store import api_key_store
        for name in ["binance", "bybit", "bitget", "gate"]:
            if not api_key_store.has_key(name):
                continue
            
            spot_client = self._exchanges.get(f"{name}_spot")
            
            future_client = None
            if name == "binance":
                if getattr(self, "_use_binance_papi", False) and "binance_papi" in self._exchanges:
                    future_client = self._exchanges.get("binance_papi")
                else:
                    future_client = self._exchanges.get("binance_linear")
            else:
                future_client = self._exchanges.get(f"{name}_linear")
            
            if not spot_client and not future_client:
                continue
            
            spot_assets = []
            contract_assets = []
            
            is_valid = False
            err_msg = ""
            
            if spot_client:
                try:
                    bal = await spot_client.fetch_balance()
                    for coin, qty in bal.get('total', {}).items():
                        if qty > 0:
                            spot_assets.append({'asset': coin, 'total': qty})
                    is_valid = True
                except Exception as e:
                    err_msg += f"Spot err: {e}. "
                    
            if future_client:
                try:
                    params = {}
                    if name == "bybit":
                        params["accountType"] = "UNIFIED"
                    bal = await future_client.fetch_balance(params=params)
                    # Gate 统一账户的 total 可能为负，取 free 才是真正可用金额
                    bal_source = bal.get('total', {})
                    if name == "gate":
                        bal_source = bal.get('free', {})
                    for coin, qty in bal_source.items():
                        if qty > 0:
                            contract_assets.append({'asset': coin, 'balance': qty})
                    is_valid = True
                except Exception as e:
                    err_msg += f"Futures err: {e}. "

            results[name] = {
                "valid": is_valid,
                "spot_assets": spot_assets,
                "contract_assets": contract_assets,
                "is_unified": True,  # 既然报错只发生在统一账户上，我们默认认定成功即统一
                "is_hedged": True,
                "error": err_msg if not is_valid else err_msg,
            }
                
        return results

    # ── 风险数据 ───────────────────────────────────────

    async def get_bn_risk_data(self, symbol: str) -> dict:
        result = {'margin_ratio': 0.0, 'adl': 0}
        client = self._exchanges.get("binance_papi")
        if not client: return result
        try:
            acct = await client.request('account', api='papi', method='GET', params={})
            uni_mmr = float(acct.get('uniMMR', 0) or 0)
            if uni_mmr > 0: result['margin_ratio'] = 1.0 / uni_mmr
        except Exception: pass
        try:
            raw_sym = symbol.replace('/', '').replace(':USDT', '')
            adl_data = await client.request('um/adlQuantile', api='papi', method='GET', params={'symbol': raw_sym})
            if isinstance(adl_data, list):
                for item in adl_data:
                    if item.get('symbol') == raw_sym:
                        q = item.get('adlQuantile', {})
                        result['adl'] = max(int(q.get('LONG', 0)), int(q.get('SHORT', 0)), int(q.get('BOTH', 0)))
                        break
        except Exception: pass
        return result


exchange_client = ExchangeClient()
