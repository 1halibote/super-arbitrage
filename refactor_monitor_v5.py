import os

file_path = r'f:\xiangmu\bn-by\backend\execution\monitor.py'

new_check_card = """    async def _check_card(self, card: TradingCard):
        active_count = self._active_tasks.get(card.id, 0)
        # 全局并发限制
        if active_count >= self.MAX_CONCURRENT_TASKS:
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
        if not opp: return

        now = time.time()
        now_ms = now * 1000

        # 未到开始时间
        if card.start_time > 0 and now_ms < card.start_time:
            return

        # ── 状态预备 ──
        pending_open = self._pending_orders.get(card.id, 0)
        pending_close = self._pending_close.get(card.id, 0)
        
        current_pos = card.position_value
        potential_pos = current_pos + pending_open
        remaining_pos = current_pos - pending_close

        # ── 开仓逻辑 (Machine Gun) ──
        spread = opp['openSpread']
        if not card.open_disabled and potential_pos < card.max_position:
            if card.last_close_time > 0 and (now_ms - card.last_close_time) < 10000:
                pass # 冷却中
            elif spread >= card.open_threshold:
                # 计算本次下单量
                room = card.max_position - potential_pos
                size = min(card.order_max, room)
                
                # 最小下单检查
                if size >= card.order_min and (potential_pos + size <= card.max_position * 1.01):
                    # 预扣减 (增加)
                    self._pending_orders[card.id] = pending_open + size
                    self._active_tasks[card.id] = active_count + 1
                    asyncio.create_task(self._do_open(card, opp, size))
                    return # 本次 Loop 只做一个动作，防止瞬间打满

        # ── 平仓逻辑 (Atomic Shot - 重构为与开仓一致) ──
        close_spread = opp.get('closeSpread', spread)
        cooldown = self._sync_throttle.get(card.id, 0)
        
        # 只要剩余仓位 > 0.05U (忽略尘埃)，且不在冷却中
        if not card.close_disabled and remaining_pos > 0.05 and now > cooldown:
            if close_spread <= card.close_threshold:
                # 计算本次平仓量
                batch = min(remaining_pos, card.order_max or remaining_pos)
                
                # 预扣减 (减少)
                self._pending_close[card.id] = pending_close + batch
                self._active_tasks[card.id] = active_count + 1 # 占用一个并发槽
                
                logging.info(f"[{symbol}] TRIGGER CLOSE SHOT: {close_spread:.2f}% <= {card.close_threshold}% batch={batch:.2f}")
                asyncio.create_task(self._do_close(card, opp, batch))
"""

new_do_close = """    async def _do_close(self, card: TradingCard, opp: dict, qty_usdt: float):
        symbol = card.symbol
        try:
            # 传递价格优化
            price_a = float(opp.get('priceA', 0))
            price_b = float(opp.get('priceB', 0))
            
            # 执行原子平仓
            res = await self.exchange.execute_arbitrage(
                card, qty_usdt=qty_usdt,
                side_a="SHORT", side_b="LONG", is_close=True,
                price_a=price_a, price_b=price_b
            )
            
            # 处理结果
            if res.status == ExecutionStatus.SUCCESS or res.status == ExecutionStatus.PARTIAL:
                filled_qty = 0.0
                filled_val = 0.0
                
                if res.order_a and res.order_a.filled_qty > 0:
                    filled_qty = res.order_a.filled_qty
                    filled_val = filled_qty * res.order_a.avg_price
                    
                    # 实时更新内存 & 广播
                    card.position_value = max(0, card.position_value - filled_val)
                    card.last_close_time = int(time.time() * 1000)
                    asyncio.create_task(self.card_mgr._broadcast(card))
                    
                    # 简易利润计算
                    snap_entry_a = card.avg_price_a or 0
                    snap_entry_b = card.avg_price_b or 0
                    snap_spread = card.open_spread or 0
                    
                    qty_b = 0
                    val_b = 0
                    if res.order_b:
                        qty_b = res.order_b.filled_qty
                        val_b = qty_b * res.order_b.avg_price
                        
                    avg_exit_a = filled_val / filled_qty if filled_qty else 0
                    avg_exit_b = val_b / qty_b if qty_b else 0
                    final_spread = (avg_exit_b - avg_exit_a) / avg_exit_a * 100 if avg_exit_a > 0 else 0
                    
                    self.card_mgr._record_profit(
                       card, filled_qty, snap_entry_a, avg_exit_a,
                       qty_b, snap_entry_b, avg_exit_b,
                       snap_spread, final_spread
                    )

            elif res.status == ExecutionStatus.FAILED:
                # 如果是 ReduceOnly 错误，说明没仓位了
                err = res.error or ''
                if "ReduceOnly" in err or "position is zero" in err:
                    # 触发一次同步
                    asyncio.create_task(self.card_mgr.sync_card(card.id))
                else:
                    logging.warning(f"[CLOSE FAIL] {symbol}: {err}")

        except Exception as e:
            logging.error(f"[CLOSE ERROR] {symbol}: {e}")
        finally:
            # 释放预扣减
            current_pending = self._pending_close.get(card.id, 0)
            self._pending_close[card.id] = max(0, current_pending - qty_usdt)
            self._active_tasks[card.id] = max(0, self._active_tasks.get(card.id, 0) - 1)
"""

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Patch __init__ (Include Type Hints)
# Match partial line to be safe
if 'self._pending_orders: Dict[str, float] = {}' in content and 'self._pending_close' not in content:
    content = content.replace('self._pending_orders: Dict[str, float] = {}', 
                              'self._pending_orders: Dict[str, float] = {}\n        self._pending_close: Dict[str, float] = {}')
elif 'self._pending_orders = {}' in content and 'self._pending_close' not in content:
     content = content.replace('self._pending_orders = {}', 'self._pending_orders = {}\n        self._pending_close = {}')

# 2. Reconstruct file
lines = content.splitlines(keepends=True)
output_lines = []
skip = False
chk_card_inserted = False
do_close_inserted = False

i = 0
while i < len(lines):
    line = lines[i]
    
    # Start checking for methods
    if 'async def _check_card(self, card: TradingCard):' in line:
        output_lines.append(new_check_card)
        chk_card_inserted = True
        skip = True
        i += 1
        continue
        
    # Logic to detect end of function being skipped
    if skip:
        # If we hit next function definition, stop skipping
        # NOTE: Be careful with nested functions or decorators
        if line.strip().startswith('async def ') or (line.strip().startswith('def ') and not line.startswith('        def ')):
             # Found next method (assuming 4 space indentation for methods)
             if line.startswith('    async def') or line.startswith('    def'):
                 skip = False
                 # Do not continue here, let it fall through to process this line
    
    if 'async def _do_close(self, card: TradingCard, opp: dict):' in line:
        output_lines.append(new_do_close)
        do_close_inserted = True
        skip = True
        i += 1
        continue
        
    if not skip:
        output_lines.append(line)
        
    i += 1

if chk_card_inserted and do_close_inserted:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    print("SUCCESS")
else:
    print("FAILED: Inserted CheckCard={}, Inserted DoClose={}".format(chk_card_inserted, do_close_inserted))

