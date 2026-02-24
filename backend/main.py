from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import sys

# Fix Windows aiodns compatibility
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

print(f"DEBUG: Loading main.py from {__file__}")


import logging
import json
import time
from contextlib import asynccontextmanager
from typing import List, Optional
from backend.execution.profit_store import profit_store, ProfitRecord

from backend.connectors.binance import BinanceClient, BinanceFutureClient
from backend.connectors.bybit import BybitClient
from backend.services.price_book import PriceBook

from backend.services.arbitrage import ArbitrageCalculator
from backend.services.feishu import feishu_notifier
from backend.execution import (
    exchange_client, card_manager, trading_monitor,
    api_key_store, TradingCard, position_ws
)

# =============================================================================
# 差价看板 (Arbitrage Dashboard)
# =============================================================================

# Global State
price_book = PriceBook()
calculator = ArbitrageCalculator(price_book)

# Feishu Config
feishu_config = {
    "enabled": False,
    "webhookUrl": "",
    "sfSpreadThreshold": 0,
    "ffSpreadThreshold": 0,
    "fundingRateThreshold": 0,
    "fundingIntervalFilter": 0,
    "indexSpreadThreshold": 0,
    "cooldownMinutes": 5,
    "blockedSymbols": [],
}

# Async Logging Setup
from backend.logging_setup import setup_async_logging
setup_async_logging()

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)


async def ticker_callback(ticker: dict):
    price_book.update(ticker)

# Exchange Clients
binance_spot = None
binance_future = None
bybit_spot = None
bybit_linear = None
bitget_spot = None
bitget_linear = None
gate_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    loop = asyncio.get_running_loop()
    
    global binance_spot, binance_future, bybit_spot, bybit_linear, bitget_spot, bitget_linear, gate_client, ping_monitor
    
    from backend.services.ping import PingMonitor
    ping_monitor = PingMonitor()
    asyncio.create_task(ping_monitor.start())
    
    binance_spot = BinanceClient(ticker_callback, loop)
    binance_future = BinanceFutureClient(ticker_callback, loop)
    bybit_spot = BybitClient("spot", ticker_callback, loop)
    bybit_linear = BybitClient("linear", ticker_callback, loop)
    
    from backend.connectors.bitget import BitgetClient
    bitget_spot = BitgetClient("spot", ticker_callback, loop)
    bitget_linear = BitgetClient("linear", ticker_callback, loop)
    
    asyncio.create_task(binance_spot.connect())
    asyncio.create_task(binance_future.connect())
    asyncio.create_task(bybit_spot.connect())
    asyncio.create_task(bybit_linear.connect())
    
    async def _safe_bitget(client, name):
        try:
            logging.info(f"[BITGET] Starting {name}...")
            await client.connect()
        except Exception as e:
            logging.error(f"[BITGET] {name} CRASHED: {e}", exc_info=True)
    
    asyncio.create_task(_safe_bitget(bitget_spot, "bitget_spot"))
    asyncio.create_task(_safe_bitget(bitget_linear, "bitget_linear"))
    
    from backend.connectors.gate import GateClient
    gate_client = GateClient(price_book)
    asyncio.create_task(gate_client.start())

    from backend.connectors.nado import NadoClient
    nado_client = NadoClient("", "default")
    nado_client.set_ticker_callback(ticker_callback)
    async def _start_nado():
        try:
            await nado_client.init()
            logging.info(f"[NADO] Init OK, {len(nado_client.price_book)} prices loaded")
            await nado_client.run_ws()
        except Exception as e:
            logging.error(f"[NADO] Startup error: {e}", exc_info=True)
    asyncio.create_task(_start_nado())

    from backend.connectors.lighter import LighterClient
    lighter_client = LighterClient()
    lighter_client.set_ticker_callback(ticker_callback)
    async def _start_lighter():
        try:
            await lighter_client.init()
            logging.info(f"[LIGHTER] Init OK, {len(lighter_client.products)} markets")
            await lighter_client.run_ws()
        except Exception as e:
            logging.error(f"[LIGHTER] Startup error: {e}", exc_info=True)
    asyncio.create_task(_start_lighter())
    
    # --- Watchdog: 清理假死/断连的交易所数据 ---
    async def watchdog_loop():
        while True:
            await asyncio.sleep(10)
            stale = price_book.clear_stale_exchanges(timeout_seconds=60)
            if stale:
                logging.error(f"[WATCHDOG] OOPS! The following exchange WS seem dead/stuck for >60s: {stale}")
                logging.error("[WATCHDOG] Stale prices removed from Arbitrage pool automatically to prevent fake signals.")
                
                # 如果配置了飞书，尝试发送报警
                if feishu_client and feishu_client.webhook_url:
                    try:
                        title = "🚨 交易所 WS 数据流断开报警"
                        text = f"以下交易所的行情在过去 60 秒没有任何更新，疑似死连接：\n**{', '.join(stale)}**\n\n系统已自动将它们从套利计算池中安全剔除。如果长时间未自动重连恢复，建议重启程序。"
                        await feishu_client.send_alert(title, text)
                    except Exception as fe:
                        logging.error(f"[WATCHDOG] Feishu alert failed: {fe}")
                        
    asyncio.create_task(watchdog_loop())
    
    asyncio.create_task(broadcast_loop())
    
    # 初始化交易引擎
    await exchange_client.initialize()
    card_manager.load_from_storage()
    exchange_client.set_price_book(price_book)

    # 启动 Position WebSocket
    position_ws.set_papi_mode(exchange_client._use_binance_papi)
    position_ws.set_on_position_update(card_manager.on_ws_position_update)
    if hasattr(position_ws, 'set_on_execution_update'):
        position_ws.set_on_execution_update(card_manager.on_execution_update)
    await position_ws.start()

    # 启动监控 + UI 广播注入
    card_manager.set_broadcast_callback(broadcast_trading_event)
    trading_monitor.set_broadcast_callback(broadcast_trading_event)
    await trading_monitor.start()
    
    # 启动后同步
    async def _initial_sync():
        await asyncio.sleep(1)
        try:
            await card_manager.sync_all_cards()
            logging.info("[INIT] 初始 Bulk Sync 完成")
        except Exception as e:
            logging.error(f"[INIT] 初始 Bulk Sync 失败: {e}")
    asyncio.create_task(_initial_sync())
    
    # Start Funding Monitor
    from backend.execution.funding_monitor import funding_monitor
    await funding_monitor.start()
    
    yield
    
    # Shutdown
    await funding_monitor.stop()
    await binance_spot.stop()
    await binance_future.stop()
    await bybit_spot.stop()
    await bybit_linear.stop()
    await bitget_spot.stop()
    await bitget_linear.stop()
    if gate_client:
        await gate_client.stop()
    await trading_monitor.stop()
    await position_ws.stop()
    await exchange_client.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Monitor WS Clients
monitor_clients: List[WebSocket] = []

@app.websocket("/ws/monitor")
async def monitor_websocket(ws: WebSocket):
    await ws.accept()
    monitor_clients.append(ws)
    try:
        # Initial status
        await ws.send_text(json.dumps({
            "type": "status",
            "data": trading_monitor.get_state()
        }))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect: pass
    finally:
        if ws in monitor_clients: monitor_clients.remove(ws)

# ── WebSocket 广播 ────────────────────────────────────

last_broadcast = {}
BROADCAST_INTERVAL = 0.5

def _pack_columnar(items: list) -> dict:
    """将 list[dict] 转换为前端期望的列式压缩格式 {cols, rows}"""
    if not items:
        return {"cols": [], "rows": []}
    cols = list(items[0].keys())
    rows = []
    for item in items:
        rows.append([item.get(c) for c in cols])
    return {"cols": cols, "rows": rows}

async def broadcast_loop():
    while True:
        try:
            # 分别计算 SF / FF / SS
            try: sf = calculator.calculate_sf()
            except Exception as e:
                logging.error(f"[SF CALC] {e}")
                sf = []
            try: ff = calculator.calculate_ff()
            except: ff = []
            try: ss = calculator.calculate_ss()
            except: ss = []

            # 更新 monitor 的 spread 数据
            for opp in sf + ff:
                trading_monitor.update_spread(opp)

            # 1. 推送到 /ws/monitor（前端主看板）
            if monitor_clients:
                update_msg = json.dumps({
                    "type": "update",
                    "data": {
                        "sf": _pack_columnar(sf),
                        "ff": _pack_columnar(ff),
                        "ss": _pack_columnar(ss),
                    }
                })
                disconnected = []
                for ws in monitor_clients:
                    try: await ws.send_text(update_msg)
                    except: disconnected.append(ws)
                for ws in disconnected:
                    monitor_clients.remove(ws)

            # 2. 推送到 /ws（旧版 spread 客户端，兼容） -> 已移除


            await feishu_notifier.check_and_notify(
                calculator.calculate_all(), feishu_config
            )
        except Exception as e:
            logging.error(f"Broadcast error: {e}")
        await asyncio.sleep(BROADCAST_INTERVAL)

# Trading WS Clients
trading_clients: List[WebSocket] = []

async def broadcast_trading_event(event: dict):
    if not trading_clients: return
    msg = json.dumps(event, default=str)
    disconnected = []
    for ws in trading_clients:
        try: await ws.send_text(msg)
        except: disconnected.append(ws)
    for ws in disconnected:
        trading_clients.remove(ws)

# ── WebSocket 端点 ────────────────────────────────────

@app.websocket("/ws/trading")
async def trading_websocket(ws: WebSocket):
    await ws.accept()
    trading_clients.append(ws)
    try:
        cards = card_manager.list_cards()
        for card in cards:
            await ws.send_text(json.dumps({
                "type": "card_update",
                "data": {"card": card.__dict__.copy()},
            }, default=str))
        while True:
            data = await ws.receive_text()
    except WebSocketDisconnect: pass
    finally:
        if ws in trading_clients: trading_clients.remove(ws)

# ── HTTP API ──────────────────────────────────────────

@app.get("/api/prices")
async def get_prices():
    prices = calculator.calculate_prices()
    return _pack_columnar(prices)

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/api/debug/bitget")
async def debug_bitget():
    result = {}
    for name, client in [("bitget_spot", bitget_spot), ("bitget_linear", bitget_linear)]:
        if client is None:
            result[name] = "NOT CREATED"
        else:
            result[name] = {
                "running": client.running,
                "symbols_count": len(client.symbols),
                "ws_connected": client.ws is not None and not client.ws.closed if client.ws else False,
                "msg_count": client.msg_count,
                "ticker_count": client.ticker_count,
                "funding_limits_count": len(client.funding_limits) if hasattr(client, "funding_limits") else 0,
                "aztec_limits": client.funding_limits.get("AZTECUSDT") if hasattr(client, "funding_limits") else None,
            }
    # 检查 price_book 里有没有 bitget 数据
    snapshot = price_book.get_snapshot()
    bg_syms = 0
    for sym, exs in snapshot.items():
        for ex in exs:
            if "bitget" in ex:
                bg_syms += 1
                break
    result["price_book_bitget_symbols"] = bg_syms
    
    # 直接检查 BTCUSDT 的所有 exchange key
    btc_data = snapshot.get("BTCUSDT", {})
    result["btcusdt_exchanges"] = list(btc_data.keys())
    
    # AZTEC 原始数据
    aztec_data = snapshot.get("AZTECUSDT", {})
    result["aztec_bitget_linear"] = aztec_data.get("bitget_linear", "MISSING")
    
    # 检查 price_book 总共有多少 symbol
    result["price_book_total_symbols"] = len(snapshot)
    
    return result

@app.get("/api/latency")
async def get_latency():
    try:
        from backend.services.ping import PingMonitor
        results = ping_monitor.get_results() if 'ping_monitor' in globals() else {}
        return {"latency": results}
    except: return {"latency": {}}

@app.get("/api/log")
async def get_logs(limit: int = 100, level: str = "ALL"):
    try:
        from backend.logging_setup import get_buffered_logs
        all_logs = get_buffered_logs()
        if level != "ALL":
            all_logs = [l for l in all_logs if l.get("level") == level]
        return {"logs": all_logs[-limit:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}

# =============================================================================
# 交易 UI (Trading Dashboard)
# =============================================================================

import uuid

class ExchangeKeyRequest(BaseModel):
    exchange: str
    apiKey: str
    apiSecret: str
    passphrase: Optional[str] = ""

class TradingCardRequest(BaseModel):
    symbol: str
    status: str = "paused"
    type: str = "SF"
    exchange_a: str = "binance"
    exchange_b: str = "bybit"
    leverage: int = 1
    open_threshold: float = 1.0
    close_threshold: float = 0.0
    max_position: float = 1000
    order_min: float = 100
    order_max: float = 500
    ladder_enabled: bool = False
    ladder: List[dict] = []
    open_disabled: bool = False
    close_disabled: bool = False
    stop_loss: float = 0
    price_alert: float = 0
    start_time: int = 0

class ExecuteOrderRequest(BaseModel):
    symbol: str
    exchangeA: str
    exchangeB: str
    qtyUsdt: float
    leverage: int = 1
    cardId: Optional[str] = None

@app.on_event("startup")
async def init_trading():
    try:
        import psutil, os
        p = psutil.Process()
        p.nice(psutil.HIGH_PRIORITY_CLASS if sys.platform == 'win32' else -10)
        if psutil.cpu_count() > 4:
            p.cpu_affinity([i for i in range(psutil.cpu_count()) if i % 2 != 0])
    except: pass

# ── 交易所管理 ────────────────────────────────────────

@app.post("/api/trading/exchange")
async def add_exchange(req: ExchangeKeyRequest):
    success = await exchange_client.add_exchange(req.exchange, req.apiKey, req.apiSecret, req.passphrase)
    return {"success": success}

@app.delete("/api/trading/exchange/{exchange}")
async def remove_exchange(exchange: str):
    await exchange_client.remove_exchange(exchange)
    return {"success": True}

@app.get("/api/trading/exchanges")
async def list_exchanges():
    exchanges = api_key_store.list_exchanges()
    balances = await exchange_client.get_balances()
    return {
        "exchanges": [
            {"name": ex, "connected": True, "balance": balances.get(ex, 0)}
            for ex in exchanges
        ]
    }

@app.get("/api/trading/balances")
async def get_balances():
    balances = await exchange_client.get_balances()
    return {"balances": balances}

# ── 卡片管理 ──────────────────────────────────────────

@app.post("/api/trading/card")
async def add_trading_card(req: TradingCardRequest):
    try:
        sym = req.symbol.upper()
        ea = req.exchange_a.lower()
        eb = req.exchange_b.lower()
        for existing in card_manager.list_cards():
            if (existing.symbol == sym and existing.type == req.type
                    and existing.exchange_a == ea and existing.exchange_b == eb):
                return {"success": False, "error": f"已存在相同配置的卡片: {sym} {req.type} {ea}/{eb}"}
        card = TradingCard(
            id=str(uuid.uuid4())[:8],
            symbol=sym,
            status=req.status, type=req.type,
            exchange_a=ea, exchange_b=eb,
            leverage=min(req.leverage, 10),
            open_threshold=req.open_threshold, close_threshold=req.close_threshold,
            max_position=req.max_position, order_min=req.order_min, order_max=req.order_max,
            ladder_enabled=req.ladder_enabled, ladder=req.ladder,
            open_disabled=req.open_disabled, close_disabled=req.close_disabled,
            stop_loss=req.stop_loss, price_alert=req.price_alert, start_time=req.start_time
        )
        card_manager.add_card(card)
        return {"success": True, "card": card.__dict__}
    except Exception as e:
        logging.error(f"Add card failed: {e}")
        return {"success": False, "error": str(e)}

from fastapi import BackgroundTasks

@app.put("/api/trading/card/{card_id}")
async def update_trading_card(card_id: str, req: TradingCardRequest, background_tasks: BackgroundTasks):
    try:
        data = {
            'status': req.status, 'open_threshold': req.open_threshold,
            'close_threshold': req.close_threshold, 'max_position': req.max_position,
            'order_min': req.order_min, 'order_max': req.order_max,
            'leverage': min(req.leverage, 10), 'stop_loss': req.stop_loss,
            'price_alert': req.price_alert, 'start_time': req.start_time,
            'ladder_enabled': req.ladder_enabled, 'ladder': req.ladder,
            'exchange_a': req.exchange_a.lower(), 'exchange_b': req.exchange_b.lower(),
            'open_disabled': req.open_disabled, 'close_disabled': req.close_disabled,
        }
        success = card_manager.update_card(card_id, data)
        if success:
            async def _sync():
                await card_manager.sync_card(card_id)
            background_tasks.add_task(_sync)
        return {"success": success}
    except Exception as e:
        logging.error(f"Update card failed: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/trading/cards")
def list_trading_cards():
    cards = card_manager.list_cards()
    return {"cards": [c.__dict__ for c in cards]}

@app.delete("/api/trading/card/{card_id}")
def delete_trading_card(card_id: str):
    card = card_manager.get_card(card_id)
    if card and card.status == "running":
        return {"success": False, "error": "Cannot delete a running card"}
    card_manager.remove_card(card_id)
    return {"success": True}

@app.post("/api/trading/card/{card_id}/reverse")
async def create_reverse_trading_card(card_id: str):
    try:
        new_card = card_manager.create_reverse_card(card_id)
        if new_card:
            return {"success": True, "card": new_card.__dict__}
        return {"success": False, "error": "Card not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/trading/card/{card_id}/toggle")
def toggle_card_status(card_id: str):
    card = card_manager.get_card(card_id)
    if not card:
        return {"success": False, "error": "Card not found"}
    card.status = "paused" if card.status == "running" else "running"
    card_manager._save()
    return {"success": True, "status": card.status}

@app.post("/api/trading/card/{card_id}/sync")
async def force_sync_card(card_id: str):
    """手动校准：从交易所拉取真实仓位并覆盖本地数据"""
    card = card_manager.get_card(card_id)
    if not card:
        return {"success": False, "error": "Card not found"}
    await card_manager.sync_card(card_id, force_overwrite=True)
    return {"success": True, "position_value": card.position_value}

@app.post("/api/trading/card/{card_id}/calibrate")
async def calibrate_card(card_id: str):
    """强制校准：对 SF 现货 A 腿也进行一次性实盘覆写，用于手动纠正账本漂移"""
    logging.warning(f"[CALIBRATE] Request received for card {card_id}")
    card = card_manager.get_card(card_id)
    if not card:
        return {"success": False, "error": "Card not found"}
    await card_manager.sync_card(card_id, force_overwrite=True, force_spot=True)
    logging.warning(f"[CALIBRATE] Done for {card_id}, val={card.position_value} val_a={card.position_value_a} qty_a={card.position_qty_a}")
    return {"success": True, "position_value": card.position_value, "position_value_a": card.position_value_a, "position_value_b": card.position_value_b}


@app.post("/api/trading/execute")
async def execute_order(req: ExecuteOrderRequest):
    card = card_manager.get_card(req.cardId) if req.cardId else card_manager.get_card_by_symbol(req.symbol.upper())
    if not card:
        card = TradingCard(
            id="manual", symbol=req.symbol.upper(),
            exchange_a=req.exchangeA.lower(), exchange_b=req.exchangeB.lower(),
            leverage=min(req.leverage, 10)
        )
    result = await exchange_client.execute_arbitrage(
        card, qty_usdt=req.qtyUsdt,
        side_a="BUY", side_b="SELL"
    )
    return {
        "success": result.status.value == "SUCCESS",
        "status": result.status.value,
        "latency_ms": result.total_latency_ms,
        "orderA": result.order_a.__dict__ if result.order_a else None,
        "orderB": result.order_b.__dict__ if result.order_b else None,
        "error": result.error
    }

@app.post("/api/trading/close/{symbol}")
async def close_position(symbol: str, exchangeA: str = "binance", exchangeB: str = "bybit", cardId: str = None):
    # 重构为策略调整模式：设置为 "只平不开"
    card = card_manager.get_card(cardId) if cardId else card_manager.get_card_by_symbol(symbol.upper())
    if not card:
        return {"success": False, "error": "Card not found"}
    
    # 修改参数：开仓999(不开)，清仓900(必平)
    card.open_threshold = 999.0
    card.close_threshold = 900.0
    card.status = "running"
    card.open_disabled = False
    card.close_disabled = False
    
    card_manager._save()
    await broadcast_trading_event({
        "type": "card_update",
        "data": {"card": card.__dict__}
    })
    
    return {
        "success": True,
        "status": "running",
        "message": "Strategy updated to CLOSE only"
    }

@app.post("/api/trading/force-close/{symbol}")
async def force_close_position(symbol: str, exchangeA: str = "binance", exchangeB: str = "bybit", cardId: str = None):
    # 同样重构为策略调整模式
    return await close_position(symbol, exchangeA, exchangeB, cardId)

# ── 持仓/资产查询 ────────────────────────────────────

@app.get("/api/trading/positions")
async def get_all_positions():
    positions = {}
    for exchange in api_key_store.list_exchanges():
        try:
            pos_map = await exchange_client.fetch_all_positions_map(exchange)
            non_zero = []
            for sym, pos_list in pos_map.items():
                for p in pos_list:
                    amt = float(p.get('contracts', 0) or p.get('positionAmt', 0) or p.get('info', {}).get('positionAmt', 0) or p.get('size', 0) or 0)
                    if abs(amt) > 0:
                        non_zero.append(p)
            positions[exchange] = non_zero
        except Exception as e:
            logging.error(f"Error getting positions for {exchange}: {e}")
            positions[exchange] = []
    return {"positions": positions}

@app.get("/api/trading/assets")
async def get_trading_assets():
    try:
        results = await exchange_client.get_assets_details()
        return {"assets": results}
    except Exception as e:
        return {"assets": {}, "error": str(e)}

# ── 监控器 API ────────────────────────────────────────

@app.get("/api/monitor/status")
def get_monitor_status():
    state = trading_monitor.get_state()
    has_api = len(api_key_store.list_exchanges()) > 0
    return {
        "status": state["status"],
        "canStart": has_api,
        "checkCount": state["check_count"],
        "triggerCount": state["trigger_count"]
    }

@app.post("/api/monitor/start")
async def start_monitor():
    await trading_monitor.start()
    return {"success": True, "status": trading_monitor.status}

@app.post("/api/feishu/config")
async def update_feishu_config(config: dict):
    global feishu_config
    feishu_config.update(config)
    return {"status": "ok", "config": feishu_config}

@app.post("/api/feishu/test")
async def test_feishu(req: dict):
    url = req.get("webhookUrl")
    if not url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing webhookUrl")
        
    success = await feishu_notifier.send_test_message(url)
    if success:
        return {"status": "ok"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to send test message")

@app.post("/api/monitor/stop")
async def stop_monitor():
    await trading_monitor.stop()
    return {"success": True, "status": trading_monitor.status}

@app.post("/api/monitor/restart")
async def restart_monitor():
    await trading_monitor.restart()
    return {"success": True, "status": trading_monitor.status}

# ── 验证 ──────────────────────────────────────────────

class VerifyRequest(BaseModel):
    exchange: str
    apiKey: str
    apiSecret: str
    passphrase: Optional[str] = ""

import ccxt.async_support as ccxt

@app.post("/api/trading/exchange/verify")
async def verify_exchange(req: VerifyRequest):
    exchange_id = req.exchange.lower()
    try:
        client = None
        if exchange_id == "binance":
            client = ccxt.binance({
                'apiKey': req.apiKey, 'secret': req.apiSecret,
                'enableRateLimit': True, 'options': {'defaultType': 'spot'}
            })
        elif exchange_id == "bybit":
            client = ccxt.bybit({
                'apiKey': req.apiKey, 'secret': req.apiSecret,
                'enableRateLimit': True, 'options': {'recvWindow': 20000}
            })
        elif exchange_id == "bitget":
            client = ccxt.bitget({
                'apiKey': req.apiKey, 'secret': req.apiSecret, 'password': req.passphrase,
                'enableRateLimit': True, 'options': {'defaultType': 'spot'}
            })
        elif exchange_id == "gate":
            client = ccxt.gate({
                'apiKey': req.apiKey, 'secret': req.apiSecret,
                'enableRateLimit': True, 'options': {'defaultType': 'spot'}
            })
        else:
            return {"valid": False, "error": f"Unsupported: {exchange_id}"}
        try:
            await client.load_markets()
            bal = await client.fetch_balance()
            spot_assets = []
            for coin, qty in bal.get('total', {}).items():
                if qty > 0:
                    spot_assets.append({'asset': coin, 'total': qty})
            
            is_unified = False
            is_hedged = True
            if exchange_id == "bybit":
                try:
                    info = await client.request('v5/user/query-api', method='GET')
                    is_unified = info.get('result', {}).get('unifiedMarginStatus', 0) in [3, 4]
                except: pass
            
            await client.close()
            return {
                "valid": True, "message": "Connected", "exchange": exchange_id,
                "spot_assets": spot_assets, "is_unified": is_unified, "is_hedged": is_hedged
            }
        except Exception as e:
            if client: await client.close()
            return {"valid": False, "error": str(e)}
    except Exception as e:
        return {"valid": False, "error": str(e)}

# ── 利润 ──────────────────────────────────────────────

@app.get("/api/profit/summary")
async def get_profit_summary():
    return profit_store.get_summary()

@app.get("/api/profit/daily")
async def get_profit_daily(date: str):
    return profit_store.get_daily_stats(date)

@app.get("/api/profit/records")
async def get_profit_records(limit: int = 50, offset: int = 0, symbol: str = None):
    try:
        records = profit_store.get_records(limit=limit, offset=offset, symbol=symbol)
        return {"records": records, "total": len(profit_store._records)}
    except Exception as e:
        return {"records": [], "error": str(e)}

@app.post("/api/profit/funding")
async def record_funding(data: dict):
    import uuid as _uuid
    record = ProfitRecord(
        id=str(_uuid.uuid4()),
        symbol=data.get("symbol", ""),
        record_type="funding",
        exchange_a=data.get("exchange_a", ""),
        exchange_b=data.get("exchange_b", ""),
        pnl=float(data.get("pnl", 0)),
        funding_rate=float(data.get("funding_rate", 0)),
        funding_income_a=float(data.get("funding_income_a", 0)),
        funding_income_b=float(data.get("funding_income_b", 0)),
        qty=float(data.get("qty", 0)),
    )
    profit_store.add_record(record)
    return {"ok": True}
