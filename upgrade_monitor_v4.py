import os

file_path = r'f:\xiangmu\bn-by\backend\execution\monitor.py'

# The new _do_close implementation with Price Passing
new_method = """    async def _do_close(self, card: TradingCard, opp: dict):
        symbol = card.symbol
        try:
            close_spread = opp.get('closeSpread', 0)
            snap_entry_a = card.avg_price_a or 0
            snap_entry_b = card.avg_price_b or 0
            snap_spread = card.open_spread or 0

            # 提前获取价格 (用于数量计算，近似值即可)
            # 使用 opp 中的价格可以避免额外的 HTTP 请求 (省去 1s+ 延迟)
            price_a = float(opp.get('priceA', 0))
            price_b = float(opp.get('priceB', 0))
            
            logging.info(f"[CLOSE START] {symbol} ApproxPrices: A={price_a} B={price_b}")

            # 统计
            total_qty_a, total_val_a = 0.0, 0.0
            total_qty_b, total_val_b = 0.0, 0.0
            total_batches = 0
            
            # 使用循环来进行"扫尾" (最多3轮)
            for rinse_round in range(3):
                # 每轮开始前，更新 remaining
                remaining = card.position_value
                if remaining <= 0.05: # 认为是尘埃，忽略(降低阈值至0.05U)
                    break
                
                max_batch = card.order_max or remaining
                
                # --- Sliding Window Logic Start ---
                tasks = set()
                MAX_CONCURRENCY = 5
                
                async def _exec_batch(batch_val):
                    try:
                        res = await self.exchange.execute_arbitrage(
                            card, qty_usdt=batch_val,
                            side_a="SHORT", side_b="LONG", is_close=True,
                            price_a=price_a, price_b=price_b # 传入价格，跳过 fetch_ticker
                        )
                        return (res, batch_val)
                    except Exception as e:
                        return (e, batch_val)

                while remaining > 0.5 or tasks:
                    # 1. Fill
                    while remaining > 0.5 and len(tasks) < MAX_CONCURRENCY:
                        batch = min(remaining, max_batch)
                        total_batches += 1
                        
                        t = asyncio.create_task(_exec_batch(batch))
                        tasks.add(t)
                        remaining -= batch 
                    
                    if not tasks: break

                    # 2. Wait First
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = pending

                    # 3. Process
                    for t in done:
                        try:
                            result_obj, batch_val = t.result()
                            
                            if isinstance(result_obj, Exception):
                                logging.error(f"[CLOSE] Round {rinse_round+1} Error: {result_obj}")
                                remaining += batch_val
                                continue
                                
                            if result_obj.status == ExecutionStatus.FAILED:
                                err = result_obj.error or ''
                                if "ReduceOnly" in err or "position is zero" in err:
                                    remaining = 0 
                                else:
                                    remaining += batch_val
                                continue

                            if result_obj.order_a and result_obj.order_a.filled_qty > 0:
                                qty = result_obj.order_a.filled_qty
                                price = result_obj.order_a.avg_price
                                val = qty * price
                                total_qty_a += qty
                                total_val_a += val
                                
                                card.position_value = max(0, card.position_value - val)
                                asyncio.create_task(self.card_mgr._broadcast(card))

                            if result_obj.order_b:
                                total_qty_b += result_obj.order_b.filled_qty
                                total_val_b += result_obj.order_b.filled_qty * result_obj.order_b.avg_price

                        except Exception as e:
                            logging.error(f"[CLOSE] Critical processing error: {e}")
                
                # --- Sliding Window Logic End ---

                # 本轮结束，立即同步状态，检查是否需要下一轮
                if rinse_round < 2:
                    await self.card_mgr.sync_card(card.id)

            # 4. 最终结算
            if total_qty_a > 0 or total_qty_b > 0:
                avg_exit_a = total_val_a / total_qty_a if total_qty_a > 0 else 0
                avg_exit_b = total_val_b / total_qty_b if total_qty_b > 0 else 0
                final_spread = (avg_exit_b - avg_exit_a) / avg_exit_a * 100 if avg_exit_a > 0 and avg_exit_b > 0 else 0

                self.card_mgr._record_profit(
                    card, total_qty_a, snap_entry_a, avg_exit_a,
                    total_qty_b, snap_entry_b, avg_exit_b,
                    snap_spread, final_spread
                )

            # 最终同步
            card.last_close_time = int(time.time() * 1000)
            await self.card_mgr.sync_card(card.id)

            logging.info(f"[CLOSE DONE] {symbol} total_batches={total_batches}")

            await self._emit_event("execution", {
                "symbol": symbol, "action": "CLOSE", "status": "DONE"
            })

        except Exception as e:
            logging.error(f"[CLOSE ERROR] {symbol}: {e}")
        finally:
            self._closing_cards.discard(card.id)
            self._active_tasks[card.id] = max(0, self._active_tasks.get(card.id, 0) - 1)
"""

# Read and Replace Logic (Same as before)
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'async def _do_close(self, card: TradingCard, opp: dict):' in line:
        start_idx = i
    if 'self._active_tasks[card.id] = max(0, self._active_tasks.get(card.id, 0) - 1)' in line:
        if i > start_idx: 
            end_idx = i

if start_idx != -1 and end_idx != -1:
    print(f"Replacing lines {start_idx+1} to {end_idx+1}")
    new_lines = lines[:start_idx] + [new_method + '\\n'] + lines[end_idx+1:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("SUCCESS")
else:
    print("FAILED to find markers")
