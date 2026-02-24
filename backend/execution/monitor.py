"""
交易监控器
负责监控卡片条件并自动执行开/平仓
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum

from .models import TradingCard, ExecutionStatus
from .card_manager import CardManager
from .exchange_client import ExchangeClient


class MonitorStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"

@dataclass
class MonitorState:
    status: MonitorStatus = MonitorStatus.STOPPED
    start_time: float = 0
    check_count: int = 0
    trigger_count: int = 0
    last_check_time: float = 0


class TradingMonitor:
    """交易监控器"""

    MAX_CONCURRENT_TASKS = 10

    def __init__(self, card_mgr: CardManager, exchange: ExchangeClient):
        self.card_mgr = card_mgr
        self.exchange = exchange
        self._state = MonitorState()
        self._task: Optional[asyncio.Task] = None

        self._spread_cache: Dict[str, Dict] = {}
        self._pending_orders: Dict[str, float] = {}
        self._pending_close: Dict[str, float] = {}
        self._active_tasks: Dict[str, int] = {}
        self._sync_throttle: Dict[str, float] = {}
        self._log_throttle: Dict[str, float] = {}
        self._last_bulk_sync: float = 0

        self._broadcast_cb = None

    def set_broadcast_callback(self, callback):
        self._broadcast_cb = callback

    async def _emit_event(self, event_type: str, data: dict):
        if self._broadcast_cb:
            try:
                await self._broadcast_cb({"type": event_type, "data": data})
            except Exception as e:
                logging.error(f"[MONITOR] Emit failed: {e}")

    # ── 状态管理 ───────────────────────────────────────

    @property
    def status(self):
        return self._state.status.value

    @property
    def is_running(self):
        return self._state.status == MonitorStatus.RUNNING

    def get_state(self):
        return {
            "status": self._state.status.value,
            "start_time": self._state.start_time,
            "check_count": self._state.check_count,
            "trigger_count": self._state.trigger_count,
            "last_check": self._state.last_check_time,
        }

    async def start(self):
        if self._state.status == MonitorStatus.RUNNING:
            return
        self._state.status = MonitorStatus.RUNNING
        self._state.start_time = time.time()
        self._task = asyncio.create_task(self._monitor_loop())
        logging.info("[MONITOR] Started")
        await self._emit_event("monitor", {"action": "started"})

    async def stop(self):
        if self._state.status == MonitorStatus.STOPPED:
            return
        self._state.status = MonitorStatus.STOPPED
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
            self._task = None
        self._pending_orders.clear()
        self._active_tasks.clear()
        self._closing_cards.clear()
        logging.info("[MONITOR] Stopped")
        await self._emit_event("monitor", {"action": "stopped"})

    async def restart(self):
        await self.stop()
        await self.start()

    def update_spread(self, opp: dict):
        symbol = opp.get('symbol', '')
        pair_key = opp.get('pair', '')
        if symbol and pair_key:
            self._spread_cache.setdefault(symbol, {})[pair_key] = opp

    # ── 监控主循环 ─────────────────────────────────────

    async def _monitor_loop(self):
        while self._state.status == MonitorStatus.RUNNING:
            try:
                await self._check_all_cards()
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[MONITOR] Loop error: {e}")
                await asyncio.sleep(1)

    async def _check_all_cards(self):
        cards = self.card_mgr.list_cards()
        running = [c for c in cards if c.status == "running"]
        if not running: return

        self._state.check_count += 1
        self._state.last_check_time = time.time()

        # 自动兜底 Sync 已移除，完全依赖本地实时扣减及手动校准

        # 并行检查
        for card in running:
            try:
                await self._check_card(card)
            except Exception as e:
                logging.error(f"[MONITOR] Check {card.symbol} error: {e}")



    # ── 条件检查 ───────────────────────────────────────

    async def _check_card(self, card: TradingCard):
        active_count = self._active_tasks.get(card.id, 0)
        
        # 预先计算潜在仓位，用于判断当前属于什么意图（开仓还是平仓）
        pending_open = self._pending_orders.get(card.id, 0)
        pending_close = self._pending_close.get(card.id, 0)
        current_pos = card.position_value
        potential_pos = current_pos + pending_open
        remaining_pos = current_pos - pending_close

        # 全局并发限制 (只限制开仓动作，平仓作为降低风险的逃生门不应受制于并发上限卡死)
        if active_count >= self.MAX_CONCURRENT_TASKS and remaining_pos <= 0.05:
            return

        symbol = card.symbol
        ex_a = card.exchange_a.lower()
        ex_b = card.exchange_b.lower()
        suffix_a = "spot" if card.type == "SF" else "linear"

        def get_key(ex, ts):
            if ex == 'binance':
                return 'binance_future' if ts == 'linear' else 'binance'
            elif ex == 'bybit':
                return 'bybit_linear' if ts == 'linear' else 'bybit_spot'
            return f"{ex}_{ts}"

        pair_key = f"{get_key(ex_a, suffix_a)}/{get_key(ex_b, 'linear')}"
        opp = self._spread_cache.get(symbol, {}).get(pair_key)
        if not opp:
            if self._state.check_count % 500 == 1:
                avail = list(self._spread_cache.get(symbol, {}).keys())
                logging.warning(f"[DBG] {symbol} want={pair_key} have={avail}")
            return

        now = time.time()
        now_ms = now * 1000

        # 未到开始时间
        if card.start_time > 0 and now_ms < card.start_time:
            return

        # 强行自愈死锁防线：如果内存独立计算的 position_value 严重偏离实际的两腿最大值，强制拉平！
        # 无论是假性满仓（偏大）还是单腿失败引发的假性空仓（被错误归零），都必须重新贴合实盘。
        ref_val = max(card.position_value_a or 0, card.position_value_b or 0)
        if abs(ref_val - card.position_value) > 0.1:
            logging.warning(f"[AUTO-FIX] Position value drifted for {symbol} ({card.position_value:.2f} -> {ref_val:.2f}U). Correcting it.")
            card.position_value = ref_val

        # ── 开仓逻辑 (Atomic Shot) ──
        # 开仓额外受制于并发限制，避免瞬间打出十几个订单
        if active_count >= self.MAX_CONCURRENT_TASKS:
            pass # 超过并发限制，跳过开仓
        else:
            spread = opp['openSpread']
        if not card.open_disabled and potential_pos < card.max_position:
            # 特权模式：如果 open_threshold <= -900，说明是用户手动点击的“一键开仓”，无视刚平完仓后的 10 秒冷却期！
            is_force_open = card.open_threshold <= -900
            if not is_force_open and card.last_close_time > 0 and (now_ms - card.last_close_time) < 10000:
                pass # 冷却中
            elif spread >= card.open_threshold:
                # 计算本次下单量
                room = card.max_position - potential_pos
                size = min(card.order_max, room)
                
                # 若剩余空间不足 order_min，但我们明确还要继续吃满最后一点，则允许该笔下单直接等于 order_min
                # 前提是他不能超出极限防爆边界 (1.1 倍最大持仓)
                if size < card.order_min and room > 0:
                    size = card.order_min
                    
                # 最小下单与安全边界检查
                if size >= card.order_min and (potential_pos + size <= card.max_position * 1.05):
                    # 预扣减 (增加)
                    self._pending_orders[card.id] = pending_open + size
                    self._active_tasks[card.id] = active_count + 1
                    asyncio.create_task(self._do_open(card, opp, size))
                    return # 本次 Loop 只做一个动作，防止瞬间打满
                elif self._state.check_count % 30 == 1:
                    logging.warning(f"[OPEN-BLOCK] {symbol} spread={spread:.3f} >= thr={card.open_threshold} BUT size={size:.1f} (min={card.order_min}) pos={potential_pos}/{card.max_position}")
            elif self._state.check_count % 30 == 1:
                logging.warning(f"[OPEN-WAIT] {symbol} spread={spread:.3f} < thr={card.open_threshold}")
        elif self._state.check_count % 30 == 1:
            logging.warning(f"[OPEN-SKIP] {symbol} disabled={card.open_disabled} pos={potential_pos}>={card.max_position}")

        # ── 平仓逻辑 (Atomic Shot) ──
        close_spread = opp.get('closeSpread', spread)
        cooldown = self._sync_throttle.get(card.id, 0)
        
        # 只要剩余仓位 > 0.05U (忽略尘埃)，且不在冷却中
        # 允许连续平仓，即如果需要多笔订单清空（比如超出了 order_max），只要 active_count < MAX_CONCURRENT_TASKS 就可以并发继续派发。
        if not card.close_disabled and remaining_pos > 0.05 and now > cooldown:
            if close_spread <= card.close_threshold:
                # 正常按策略平仓（包括一键清仓）：必须受制于 order_max 分批，防止一次性砸盘造成巨大滑点！
                batch = min(remaining_pos, card.order_max or remaining_pos)
                
                # 兜底合并 1: 如果这次发完单以后，剩下的零头不足 order_min，干脆这次一起平了，免得剩下粉尘卖不掉被卡住
                if remaining_pos - batch < card.order_min and remaining_pos - batch > 0:
                    batch = remaining_pos

                # 兜底合并 2: 如果本身就不足 order_min，补足到 order_min 发出（满足交易所 MIN_NOTIONAL）
                if batch < card.order_min and batch > 0:
                    batch = max(card.order_min, remaining_pos) 
                
                # 预扣减 (减少)
                self._pending_close[card.id] = pending_close + batch
                self._active_tasks[card.id] = active_count + 1 # 占用一个并发槽
                
                logging.info(f"[{symbol}] TRIGGER CLOSE SHOT: {close_spread:.4f}% <= {card.close_threshold:.4f}% batch={batch:.2f} (rem={remaining_pos:.2f})")
                asyncio.create_task(self._do_close(card, opp, batch))
                return # 每轮 loop 只发射一枪，下个毫秒级 loop 继续发射，防止触碰交易所 rate limit
    async def _do_open(self, card: TradingCard, opp: dict, qty_usdt: float):
        symbol = card.symbol
        try:
            # 开仓：A腿买入用 askA，B腿做空用 bidB（直接使用 ws 实时价格，免除 REST fetch_ticker 延迟）
            price_a = float(opp.get('askA') or opp.get('priceA', 0))
            price_b = float(opp.get('bidB') or opp.get('priceB', 0))
            spread = opp['openSpread']

            # 合约的 filled_qty 是张数，需要乘以 contractSize 才能得到真实币数
            def _contract_size(ex_key):
                if ('gate' not in ex_key and 'bitget' not in ex_key) or 'spot' in ex_key:
                    return 1.0
                client = self.exchange.get_client(ex_key)
                if not client:
                    return 1.0
                try:
                    base = symbol[:-4] if symbol.endswith('USDT') else symbol
                    ccxt_sym = f"{base}/USDT:USDT"
                    return client.market(ccxt_sym).get('contractSize', 1) or 1
                except Exception:
                    return 1.0

            suffix_a = 'spot' if card.type == 'SF' else 'linear'
            def _mk_key(ex, ts):
                if ex == 'binance': return 'binance_future' if ts == 'linear' else 'binance'
                if ex == 'bybit': return 'bybit_linear' if ts == 'linear' else 'bybit_spot'
                return f"{ex}_{ts}"
            ex_key_a = _mk_key(card.exchange_a, suffix_a)
            ex_key_b = _mk_key(card.exchange_b, 'linear')
            cs_a = _contract_size(ex_key_a)
            cs_b = _contract_size(ex_key_b)

            logging.info(f"[OPEN] {symbol} Spread={spread:.4f}% Qty={qty_usdt:.1f}U cs_a={cs_a} cs_b={cs_b} exA={ex_key_a} exB={ex_key_b}")

            await self._emit_event("trigger", {
                "symbol": symbol, "action": "OPEN",
                "spread": spread, "threshold": card.open_threshold
            })

            result = await self.exchange.execute_arbitrage(
                card, qty_usdt=qty_usdt,
                side_a="BUY", side_b="SELL",
                price_a=price_a, price_b=price_b
            )

            if result.status == ExecutionStatus.SUCCESS:
                card._fail_count = 0
                self._state.trigger_count += 1
                self._sync_throttle[card.id] = time.time() + 3.0

                val_shot_a, val_shot_b = 0.0, 0.0
                if result.order_a:
                    if result.order_a.filled_qty <= 0 or result.order_a.avg_price <= 0:
                        result.order_a.filled_qty = qty_usdt / price_a if price_a else 0
                        result.order_a.avg_price = price_a
                    
                    # 绝对禁止使用 CCXT order.cost (对 Gate/Bitget 等合约该字段没有乘面值，单位也是错乱的)
                    val_shot_a = result.order_a.filled_qty * result.order_a.avg_price * cs_a
                    card.position_value_a = (card.position_value_a or 0) + val_shot_a
                    card.position_qty_a = (card.position_qty_a or 0) + result.order_a.filled_qty
                    if card.position_qty_a > 0:
                        real_qty = card.position_qty_a * cs_a
                        card.avg_price_a = card.position_value_a / real_qty if real_qty > 0 else 0
                    
                if result.order_b:
                    if result.order_b.filled_qty <= 0 or result.order_b.avg_price <= 0:
                        result.order_b.filled_qty = qty_usdt / price_b if price_b else 0
                        result.order_b.avg_price = price_b
                    
                    val_shot_b = result.order_b.filled_qty * result.order_b.avg_price * cs_b
                    card.position_value_b = (card.position_value_b or 0) + val_shot_b
                    card.position_qty_b = (card.position_qty_b or 0) + result.order_b.filled_qty
                    if card.position_qty_b > 0:
                        real_qty = card.position_qty_b * cs_b
                        card.avg_price_b = card.position_value_b / real_qty if real_qty > 0 else 0

                # 用实际成交价値（FF/SF 通用），防止 Sync 后 position_value 被错误括高
                filled = max(val_shot_a, val_shot_b) or qty_usdt
                card.position_value += filled
                card.open_spread = spread
                card.last_open_time = int(time.time() * 1000)

                logging.info(f"[OPEN OK] {symbol} {filled:.1f}U (pos={card.position_value:.1f}/{card.max_position:.1f})")
                asyncio.create_task(self.card_mgr._broadcast(card))

            elif result.status == ExecutionStatus.PARTIAL:
                card._fail_count = 0
                self._state.trigger_count += 1
                val_shot_a, val_shot_b = 0.0, 0.0
                if result.order_a:
                    if result.order_a.filled_qty <= 0 or result.order_a.avg_price <= 0:
                        result.order_a.filled_qty = qty_usdt / price_a if price_a else 0
                        result.order_a.avg_price = price_a
                    
                    val_shot_a = result.order_a.filled_qty * result.order_a.avg_price * cs_a
                    card.position_value_a = (card.position_value_a or 0) + val_shot_a
                    card.position_qty_a = (card.position_qty_a or 0) + result.order_a.filled_qty
                    if card.position_qty_a > 0:
                        real_qty = card.position_qty_a * cs_a
                        card.avg_price_a = card.position_value_a / real_qty if real_qty > 0 else 0
                    
                if result.order_b:
                    if result.order_b.filled_qty <= 0 or result.order_b.avg_price <= 0:
                        result.order_b.filled_qty = qty_usdt / price_b if price_b else 0
                        result.order_b.avg_price = price_b
                    
                    val_shot_b = result.order_b.filled_qty * result.order_b.avg_price * cs_b
                    card.position_value_b = (card.position_value_b or 0) + val_shot_b
                    card.position_qty_b = (card.position_qty_b or 0) + result.order_b.filled_qty
                    if card.position_qty_b > 0:
                        real_qty = card.position_qty_b * cs_b
                        card.avg_price_b = card.position_value_b / real_qty if real_qty > 0 else 0
                    
                card.position_value += (max(val_shot_a, val_shot_b) or qty_usdt * 0.5)
                card.open_spread = spread
                card.last_open_time = int(time.time() * 1000)
                logging.warning(f"[OPEN PARTIAL] {symbol} Error={result.error} (a={val_shot_a:.1f},b={val_shot_b:.1f})")
                asyncio.create_task(self.card_mgr._broadcast(card))

            else:
                logging.error(f"[OPEN FAIL] {symbol} error={result.error}")
                fail_count = getattr(card, '_fail_count', 0) + 1
                card._fail_count = fail_count
                if fail_count >= 3:
                    card.status = "paused"
                    card.open_disabled = True
                    card.close_disabled = True
                    card._fail_count = 0
                    logging.critical(f"[CIRCUIT BREAKER] {symbol} 连续开仓失败触达 3 次！卡片已被强制暂停！")
                    asyncio.create_task(self.card_mgr.update_card(card.id, {"status": "paused", "open_disabled": True, "close_disabled": True}))
                    asyncio.create_task(self.card_mgr._broadcast(card))
                else:
                    self._sync_throttle[card.id] = time.time() + 10.0
                    logging.warning(f"[OPEN BLOCK] {symbol} 被施加 10s 冷却，当前连续失败次数: {fail_count} / 3")

        except Exception as e:
            logging.error(f"[OPEN ERROR] {symbol}: {e}")
        finally:
            self._pending_orders[card.id] = max(0, self._pending_orders.get(card.id, 0) - qty_usdt)
            self._active_tasks[card.id] = max(0, self._active_tasks.get(card.id, 0) - 1)

    # ── 平仓执行 ───────────────────────────────────────

    async def _do_close(self, card: TradingCard, opp: dict, qty_usdt: float):
        symbol = card.symbol
        try:
            # 传递价格优化
            # 平仓：A腿卖出用 bidA，B腿平空用 askB
            price_a = float(opp.get('bidA') or opp.get('priceA', 0))
            price_b = float(opp.get('askB') or opp.get('priceB', 0))

            # 执行原子平仓
            res = await self.exchange.execute_arbitrage(
                card, qty_usdt=qty_usdt,
                side_a="SHORT", side_b="LONG", is_close=True,
                price_a=price_a, price_b=price_b
            )
            
            # 处理结果
            if res.status == ExecutionStatus.SUCCESS or res.status == ExecutionStatus.PARTIAL:
                card._fail_count = 0
                
                # 提取面值，应对从 cost 平仓金额提取
                def _cs(ex, ts):
                    if ('gate' not in ex and 'bitget' not in ex) or 'spot' in ts: return 1.0
                    c = self.exchange.get_client(f"{ex}_{ts}")
                    if c:
                        try:
                            base = symbol[:-4] if symbol.endswith('USDT') else symbol
                            return float(c.markets.get(f"{base}/USDT:USDT", {}).get('contractSize') or 1)
                        except: pass
                    return 1.0

                type_a = 'spot' if card.type == 'SF' else 'linear'
                cs_a = _cs(card.exchange_a, type_a)
                cs_b = _cs(card.exchange_b, 'linear')
                
                filled_qty_a = 0.0
                filled_val_a = 0.0
                qty_b = 0.0
                val_b = 0.0

                if res.order_a:
                    filled_qty_a = res.order_a.filled_qty
                    actual_price_a = res.order_a.avg_price if res.order_a.avg_price and res.order_a.avg_price > 0 else price_a
                    
                    if filled_qty_a <= 0 and res.status == ExecutionStatus.SUCCESS:
                         filled_qty_a = qty_usdt / actual_price_a if actual_price_a > 0 else 0
                    
                    if filled_qty_a > 0:
                        # 禁止采纳 ccxt 原生 cost！自己乘面值和价格最稳妥
                        filled_val_a = filled_qty_a * actual_price_a * cs_a
                        card.position_value_a = max(0, (card.position_value_a or 0) - filled_val_a)
                        card.position_qty_a = max(0, (card.position_qty_a or 0) - filled_qty_a)

                if res.order_b:
                    qty_b = res.order_b.filled_qty
                    actual_price_b = res.order_b.avg_price if res.order_b.avg_price and res.order_b.avg_price > 0 else price_b
                    
                    if qty_b <= 0 and res.status == ExecutionStatus.SUCCESS:
                         qty_b = qty_usdt / actual_price_b if actual_price_b > 0 else 0

                    if qty_b > 0:
                        val_b = qty_b * actual_price_b * cs_b
                        card.position_value_b = max(0, (card.position_value_b or 0) - val_b)
                        card.position_qty_b = max(0, (card.position_qty_b or 0) - qty_b)

                # 确保 position_value 反映真实的两腿最大敞口
                card.position_value = max(card.position_value_a or 0, card.position_value_b or 0)
                card.last_close_time = int(time.time() * 1000)
                actual_closed_val = max(filled_val_a, val_b)
                logging.info(f"[CLOSE OK] {symbol} {actual_closed_val:.1f}U (pos={card.position_value:.1f}/{card.max_position:.1f})")
                asyncio.create_task(self.card_mgr._broadcast(card))

                # 轮回利润累加与计算
                if filled_qty_a > 0 or qty_b > 0:
                    if not hasattr(card, '_cycle_profit_data'):
                        card._cycle_profit_data = {
                            'qty_a': 0.0, 'val_a': 0.0, 'entry_a': card.avg_price_a or 0,
                            'qty_b': 0.0, 'val_b': 0.0, 'entry_b': card.avg_price_b or 0,
                            'open_spread': card.open_spread or 0
                        }
                    
                    # 持续累加本次的平仓数量和获得的价值
                    card._cycle_profit_data['qty_a'] += filled_qty_a
                    card._cycle_profit_data['val_a'] += filled_val_a
                    card._cycle_profit_data['qty_b'] += qty_b
                    card._cycle_profit_data['val_b'] += val_b
                    
                    # 判断如果本次平仓导致卡片整体主要仓位归零，或者合约腿完全清零，则进行结算
                    if card.position_value <= 5.0 or (card.position_qty_b or 0) <= 0.0001:
                        cp = card._cycle_profit_data
                        
                        real_qty_a = cp['qty_a'] * cs_a
                        real_qty_b = cp['qty_b'] * cs_b
                        
                        # 计算这个周期的平均平仓价格
                        avg_exit_a = cp['val_a'] / real_qty_a if real_qty_a > 0 else 0
                        avg_exit_b = cp['val_b'] / real_qty_b if real_qty_b > 0 else 0
                        
                        final_spread = (avg_exit_b - avg_exit_a) / avg_exit_a * 100 if avg_exit_a > 0 else 0
                        
                        self.card_mgr._record_profit(
                           card,
                           cp['qty_a'] or cp['qty_b'], cp['entry_a'], avg_exit_a,
                           cp['qty_b'] or cp['qty_a'], cp['entry_b'], avg_exit_b,
                           cp['open_spread'], final_spread
                        )
                        # 结算后清空周期累计缓存及内存残渣
                        delattr(card, '_cycle_profit_data')
                        card.position_qty_a, card.position_value_a = 0, 0
                        card.position_qty_b, card.position_value_b = 0, 0
                        card.position_value = 0

            elif res.status == ExecutionStatus.FAILED:
                err = res.error or ''
                if "ReduceOnly" in err or "position is zero" in err or "balance=0" in err:
                    # 如果真的没仓位了，触发一次强制同步校准
                    asyncio.create_task(self.card_mgr.sync_card(card.id))
                    
                    # 容错：防止因最后一枪报错导致已经累加的部分利润无法结单
                    if hasattr(card, '_cycle_profit_data'):
                        cp = card._cycle_profit_data
                        if cp['qty_a'] > 0 or cp['qty_b'] > 0:
                            def _cs(ex, ts):
                                if ('gate' not in ex and 'bitget' not in ex) or 'spot' in ts: return 1.0
                                c = self.exchange.get_client(f"{ex}_{ts}")
                                if c:
                                    try:
                                        base = symbol[:-4] if symbol.endswith('USDT') else symbol
                                        return float(c.markets.get(f"{base}/USDT:USDT", {}).get('contractSize') or 1)
                                    except: pass
                                return 1.0

                            type_a = 'spot' if card.type == 'SF' else 'linear'
                            cs_a = _cs(card.exchange_a, type_a)
                            cs_b = _cs(card.exchange_b, 'linear')

                            real_qty_a = cp['qty_a'] * cs_a
                            real_qty_b = cp['qty_b'] * cs_b
                            
                            avg_exit_a = cp['val_a'] / real_qty_a if real_qty_a > 0 else 0
                            avg_exit_b = cp['val_b'] / real_qty_b if real_qty_b > 0 else 0
                            final_spread = (avg_exit_b - avg_exit_a) / avg_exit_a * 100 if avg_exit_a > 0 else 0
                            self.card_mgr._record_profit(
                               card,
                               cp['qty_a'] or cp['qty_b'], cp['entry_a'], avg_exit_a,
                               cp['qty_b'] or cp['qty_a'], cp['entry_b'], avg_exit_b,
                               cp['open_spread'], final_spread
                            )
                        delattr(card, '_cycle_profit_data')
                        card.position_qty_a, card.position_value_a = 0, 0
                        card.position_qty_b, card.position_value_b = 0, 0
                        card.position_value = 0
                else:
                    logging.warning(f"[CLOSE FAIL] {symbol}: {err}")
                    fail_count = getattr(card, '_fail_count', 0) + 1
                    card._fail_count = fail_count
                    if fail_count >= 3:
                        card.status = "paused"
                        card.open_disabled = True
                        card.close_disabled = True
                        card._fail_count = 0
                        logging.critical(f"[CIRCUIT BREAKER] {symbol} 连续平仓失败触达 3 次！卡片已被强制暂停！")
                        asyncio.create_task(self.card_mgr.update_card(card.id, {"status": "paused", "open_disabled": True, "close_disabled": True}))
                        asyncio.create_task(self.card_mgr._broadcast(card))
                    else:
                        self._sync_throttle[card.id] = time.time() + 10.0
                        logging.warning(f"[CLOSE BLOCK] {symbol} 被施加 10s 冷却，当前连续失败次数: {fail_count} / 3")

        except Exception as e:
            logging.error(f"[CLOSE ERROR] {symbol}: {e}")
        finally:
            # 无论成功失败，释放预扣减的额度和并发槽位
            current_pending = self._pending_close.get(card.id, 0)
            self._pending_close[card.id] = max(0, current_pending - qty_usdt)
            self._active_tasks[card.id] = max(0, self._active_tasks.get(card.id, 0) - 1)
