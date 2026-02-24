"""
Position WebSocket Manager
通过 private WebSocket 实时接收仓位变更，替代 REST API 轮询。
- Bybit: wss://stream.bybit.com/v5/private -> position topic
- Binance Futures: listenKey -> wss://fstream.binance.com/ws/<key> -> ACCOUNT_UPDATE
- Binance PAPI: listenKey -> wss://fstream.binance.com/pm/ws/<key> -> ACCOUNT_UPDATE
"""

import asyncio
import json
import time
import hmac
import hashlib
import logging
from typing import Dict, Optional, Callable

import aiohttp
import websockets

from .key_store import api_key_store


class PositionWSManager:
    def __init__(self):
        self._positions: Dict[str, Dict[str, dict]] = {}
        self._balances: Dict[str, Dict[str, dict]] = {}
        self._running = False
        self._tasks = []
        self._last_update: Dict[str, float] = {}
        self._connected: Dict[str, bool] = {}
        self._use_papi = False
        self._on_position_update: Optional[Callable] = None

    def set_papi_mode(self, enabled: bool):
        self._use_papi = enabled

    def set_on_position_update(self, callback: Callable):
        self._on_position_update = callback

    def get_position(self, exchange_key: str, symbol: str) -> Optional[dict]:
        """获取指定交易所+symbol的仓位"""
        return self._positions.get(exchange_key, {}).get(symbol)

    def get_all_positions(self, exchange_key: str) -> Dict[str, dict]:
        """获取指定交易所的所有仓位"""
        return self._positions.get(exchange_key, {})

    def get_balance(self, exchange_key: str, currency: str) -> Optional[dict]:
        """获取指定交易所的某币种余额"""
        return self._balances.get(exchange_key, {}).get(currency)

    def is_alive(self, exchange_key: str, max_age: float = 120.0) -> bool:
        """检查 WS 连接是否活跃（基于连接状态 + 数据新鲜度）"""
        if self._connected.get(exchange_key):
            return True
        ts = self._last_update.get(exchange_key, 0)
        return (time.time() - ts) < max_age

    async def start(self):
        if self._running:
            return
        self._running = True

        # Bybit
        bybit_keys = api_key_store.get_key("bybit")
        if bybit_keys:
            t = asyncio.create_task(self._run_bybit_private(
                bybit_keys["api_key"], bybit_keys["api_secret"]
            ))
            self._tasks.append(t)
            logging.info("[POS_WS] Bybit private WS task started")

        # Binance
        bn_keys = api_key_store.get_key("binance")
        if bn_keys:
            t = asyncio.create_task(self._run_binance_user_stream(
                bn_keys["api_key"], bn_keys["api_secret"]
            ))
            self._tasks.append(t)
            logging.info("[POS_WS] Binance user data stream task started")

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    # ===================== Bybit Private WS =====================

    async def _run_bybit_private(self, api_key: str, api_secret: str):
        ws_url = "wss://stream.bybit.com/v5/private"

        while self._running:
            try:
                logging.info(f"[POS_WS] Connecting to Bybit private WS...")
                # Reduced ping interval to 5s to solve 20s delay issue
                async with websockets.connect(ws_url, ping_interval=5, ping_timeout=5) as ws:
                    # 认证
                    expires = int((time.time() + 10) * 1000)
                    sign_str = f"GET/realtime{expires}"
                    signature = hmac.new(
                        api_secret.encode(), sign_str.encode(), hashlib.sha256
                    ).hexdigest()

                    auth_msg = {
                        "op": "auth",
                        "args": [api_key, expires, signature]
                    }
                    await ws.send(json.dumps(auth_msg))

                    # 等待认证响应
                    auth_resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    auth_data = json.loads(auth_resp)
                    if not auth_data.get("success", False):
                        logging.error(f"[POS_WS] Bybit auth failed: {auth_data}")
                        await asyncio.sleep(5)
                        continue

                    logging.info("[POS_WS] Bybit auth OK, subscribing to position...")
                    self._connected["bybit_linear"] = True

                    # 订阅 position 和 execution
                    sub_msg = {"op": "subscribe", "args": ["position", "execution"]}
                    await ws.send(json.dumps(sub_msg))

                    # 启动心跳
                    heartbeat = asyncio.create_task(self._bybit_heartbeat(ws))

                    try:
                        while self._running:
                            msg = await ws.recv()
                            data = json.loads(msg)

                            topic = data.get("topic")
                            if topic == "position":
                                self._handle_bybit_position(data.get("data", []))
                            elif topic == "execution":
                                self._handle_bybit_execution(data.get("data", []))
                    except Exception as e:
                        if "1006" not in str(e) and "no close frame" not in str(e):
                            logging.error(f"[POS_WS] Bybit recv error: {e}")
                    finally:
                        heartbeat.cancel()
                        self._connected["bybit_linear"] = False

            except Exception as e:
                logging.error(f"[POS_WS] Bybit connection error: {e}")
            
            if self._running:
                await asyncio.sleep(3)

    def _handle_bybit_execution(self, executions: list):
        """处理 Bybit 成交推送"""
        if not executions: return
        # Log first execution to confirm receipt
        logging.info(f"[EXEC_WS] Bybit Execution: {executions[0].get('symbol')} {executions[0].get('side')} {executions[0].get('execQty')}")
        
        # Trigger externally?
        # We need a way to notify Executor to sync this symbol.
        if hasattr(self, '_on_execution_update') and self._on_execution_update:
             try:
                 if asyncio.iscoroutinefunction(self._on_execution_update):
                     asyncio.create_task(self._on_execution_update('bybit_linear', executions))
                 else:
                     self._on_execution_update('bybit_linear', executions)
             except Exception as e:
                 logging.error(f"[EXEC_WS] Callback error: {e}")

    async def _bybit_heartbeat(self, ws):
        while True:
            await asyncio.sleep(5)
            try:
                await ws.send(json.dumps({"op": "ping"}))
            except:
                break

    def _handle_bybit_position(self, positions: list):
        """处理 Bybit position 推送"""
        ex_key = "bybit_linear"
        if ex_key not in self._positions:
            self._positions[ex_key] = {}

        for pos in positions:
            symbol = pos.get("symbol", "")
            side = pos.get("side", "").lower()  # Buy/Sell -> buy/sell
            size = float(pos.get("size", 0) or 0)
            entry_price = float(pos.get("entryPrice", 0) or 0)
            value = float(pos.get("positionValue", 0) or 0)
            pnl = float(pos.get("unrealisedPnl", 0) or 0)
            liq_price = float(pos.get("liqPrice", 0) or 0)

            pos_side = "long" if side == "buy" else "short"

            # 用 symbol+side 作为 key，支持 hedge mode
            pos_key = f"{symbol}_{pos_side}"

            if size == 0:
                self._positions[ex_key].pop(pos_key, None)
            else:
                self._positions[ex_key][pos_key] = {
                    "symbol": symbol,
                    "side": pos_side,
                    "qty": size,
                    "value": value,
                    "pnl": pnl,
                    "entry_price": entry_price,
                    "liq_price": liq_price,
                    "updated_at": time.time()
                }

        self._last_update[ex_key] = time.time()
        logging.debug(f"[POS_WS] Bybit position update: {len(self._positions[ex_key])} active")
        
        # Notify Listener
        if self._on_position_update:
            # Flatten to list of dicts for subscriber
            updates = []
            for k, v in self._positions[ex_key].items():
                 updates.append(v)
            try:
                if asyncio.iscoroutinefunction(self._on_position_update):
                    asyncio.create_task(self._on_position_update(ex_key, updates))
                else:
                    self._on_position_update(ex_key, updates)
            except Exception as e:
                logging.error(f"[POS_WS] Callback error: {e}")

    # ===================== Binance User Data Stream =====================

    async def _run_binance_user_stream(self, api_key: str, api_secret: str):
        while self._running:
            try:
                # 获取 / 创建 listenKey
                listen_key = await self._get_binance_listen_key(api_key)
                if not listen_key:
                    # Logging handled in _get_binance_listen_key
                    # If 401/Invalid Key, sleep longer to avoid spam
                    logging.warning("[POS_WS] Binance listenKey failed. Sleeping 60s...")
                    await asyncio.sleep(60)
                    continue

                # 选择 WS URL
                if self._use_papi:
                    ws_url = f"wss://fstream.binance.com/pm/ws/{listen_key}"
                else:
                    ws_url = f"wss://fstream.binance.com/ws/{listen_key}"

                logging.info(f"[POS_WS] Connecting to Binance user stream (PAPI={self._use_papi})...")
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    logging.info("[POS_WS] Binance user stream connected")
                    self._connected["binance_linear"] = True
                    self._connected["binance_spot"] = True

                    # listenKey 30 min 续期
                    renew_task = asyncio.create_task(
                        self._renew_binance_listen_key(api_key, listen_key)
                    )

                    try:
                        while self._running:
                            msg = await ws.recv()
                            data = json.loads(msg)
                            event_type = data.get("e", "")

                            if event_type == "ACCOUNT_UPDATE":
                                self._handle_binance_account_update(data)
                            elif event_type == "listenKeyExpired":
                                logging.warning("[POS_WS] Binance listenKey expired, reconnecting...")
                                break
                    except Exception as e:
                        if "1006" not in str(e):
                            logging.error(f"[POS_WS] Binance recv error: {e}")
                    finally:
                        renew_task.cancel()
                        self._connected["binance_linear"] = False
                        self._connected["binance_spot"] = False

            except Exception as e:
                logging.error(f"[POS_WS] Binance connection error: {e}")

            if self._running:
                await asyncio.sleep(3)

    async def _get_binance_listen_key(self, api_key: str) -> Optional[str]:
        """创建 Binance listenKey"""
        if self._use_papi:
            url = "https://papi.binance.com/papi/v1/listenKey"
        else:
            url = "https://fapi.binance.com/fapi/v1/listenKey"

        headers = {"X-MBX-APIKEY": api_key}
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.post(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        key = data.get("listenKey", "")
                        logging.info(f"[POS_WS] Binance listenKey obtained: {key[:8]}...")
                        return key
                    else:
                        text = await resp.text()
                        if resp.status == 401 or resp.status == 403:
                             logging.warning(f"[POS_WS] Binance listenKey Auth Error {resp.status}: {text} (Check API Key)")
                        else:
                             logging.error(f"[POS_WS] Binance listenKey error {resp.status}: {text}")
                        return None
        except Exception as e:
            logging.error(f"[POS_WS] Binance listenKey request failed: {e}")
            return None

    async def _renew_binance_listen_key(self, api_key: str, listen_key: str):
        """每 30 分钟续期 listenKey"""
        if self._use_papi:
            url = "https://papi.binance.com/papi/v1/listenKey"
        else:
            url = "https://fapi.binance.com/fapi/v1/listenKey"

        headers = {"X-MBX-APIKEY": api_key}
        while self._running:
            await asyncio.sleep(1800)  # 30min
            try:
                async with aiohttp.ClientSession(trust_env=True) as session:
                    async with session.put(url, headers=headers) as resp:
                        if resp.status == 200:
                            logging.info("[POS_WS] Binance listenKey renewed")
                        else:
                            text = await resp.text()
                            logging.warning(f"[POS_WS] Binance listenKey renew failed: {text}")
            except Exception as e:
                logging.error(f"[POS_WS] Binance listenKey renew error: {e}")

    def _handle_binance_account_update(self, data: dict):
        """处理 Binance ACCOUNT_UPDATE"""
        account = data.get("a", {})

        # 余额更新
        balances = account.get("B", [])
        for bal in balances:
            asset = bal.get("a", "")  # e.g. "USDT", "BTC"
            wb = float(bal.get("wb", 0) or 0)  # wallet balance
            cw = float(bal.get("cw", 0) or 0)  # cross wallet balance

            ex_key = "binance_spot"
            if ex_key not in self._balances:
                self._balances[ex_key] = {}
            self._balances[ex_key][asset] = {
                "total": wb,
                "free": cw,
                "updated_at": time.time()
            }

        # 仓位更新
        positions = account.get("P", [])
        ex_key = "binance_linear"
        if ex_key not in self._positions:
            self._positions[ex_key] = {}

        for pos in positions:
            symbol = pos.get("s", "")
            pa = float(pos.get("pa", 0) or 0)  # position amount (signed)
            ep = float(pos.get("ep", 0) or 0)  # entry price
            up = float(pos.get("up", 0) or 0)  # unrealized PnL
            ps = pos.get("ps", "BOTH")  # position side: LONG/SHORT/BOTH

            if ps == "LONG":
                pos_side = "long"
            elif ps == "SHORT":
                pos_side = "short"
            else:
                pos_side = "long" if pa >= 0 else "short"

            pos_key = f"{symbol}_{pos_side}"
            abs_qty = abs(pa)

            if abs_qty == 0:
                self._positions[ex_key].pop(pos_key, None)
            else:
                value = abs_qty * ep if ep > 0 else 0
                self._positions[ex_key][pos_key] = {
                    "symbol": symbol,
                    "side": pos_side,
                    "qty": abs_qty,
                    "value": value,
                    "pnl": up,
                    "entry_price": ep,
                    "liq_price": 0,
                    "updated_at": time.time()
                }

        self._last_update[ex_key] = time.time()
        logging.debug(f"[POS_WS] Binance position update: {len(self._positions.get(ex_key, {}))} active")

        # Notify Listener
        if self._on_position_update:
            # Flatten to list
            updates = []
            for k, v in self._positions.get(ex_key, {}).items():
                 updates.append(v)
            try:
                if asyncio.iscoroutinefunction(self._on_position_update):
                    asyncio.create_task(self._on_position_update(ex_key, updates))
                else:
                    self._on_position_update(ex_key, updates)
            except Exception as e:
                logging.error(f"[POS_WS] Callback error: {e}")


# 全局实例
position_ws = PositionWSManager()
