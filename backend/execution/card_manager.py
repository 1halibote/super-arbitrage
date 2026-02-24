"""
卡片管理 + 仓位同步 + 利润记录
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Callable

from .models import TradingCard, ExecutionResult, ExecutionStatus
from .exchange_client import ExchangeClient
from .card_store import card_store
from .profit_store import profit_store, ProfitRecord
from backend.services.fee_utils import get_fee_rate


class CardManager:
    """卡片生命周期管理 + 仓位同步"""

    def __init__(self, exchange: ExchangeClient):
        self.exchange = exchange
        self._cards: Dict[str, TradingCard] = {}
        self._sync_throttle: Dict[str, float] = {}
        self._broadcast_cb: Optional[Callable] = None

    def set_broadcast_callback(self, cb):
        self._broadcast_cb = cb

    # ── 卡片 CRUD ──────────────────────────────────────

    def add_card(self, card: TradingCard):
        self._cards[card.id] = card
        self._save()

    def get_card(self, card_id: str) -> Optional[TradingCard]:
        return self._cards.get(card_id)

    def get_card_by_symbol(self, symbol: str) -> Optional[TradingCard]:
        for card in self._cards.values():
            if card.symbol == symbol:
                return card
        return None

    def list_cards(self) -> List[TradingCard]:
        return list(self._cards.values())

    def update_card(self, card_id: str, data: dict):
        """更新卡片配置字段"""
        card = self._cards.get(card_id)
        if not card: return False
        config_fields = [
            'status', 'open_threshold', 'close_threshold', 'max_position',
            'order_min', 'order_max', 'leverage', 'stop_loss', 'price_alert',
            'start_time', 'ladder_enabled', 'ladder', 'exchange_a', 'exchange_b',
            'open_disabled', 'close_disabled',
        ]
        for k in config_fields:
            if k in data:
                setattr(card, k, data[k])
        self._save()
        return True

    def remove_card(self, card_id: str):
        self._cards.pop(card_id, None)
        self._save()

    def create_reverse_card(self, card_id: str) -> Optional[TradingCard]:
        original = self._cards.get(card_id)
        if not original: return None
        new_card = TradingCard(
            id=str(uuid.uuid4()), symbol=original.symbol, type=original.type,
            exchange_a=original.exchange_b, exchange_b=original.exchange_a,
            status="paused", leverage=original.leverage,
            open_threshold=original.open_threshold, close_threshold=original.close_threshold,
            max_position=original.max_position, order_min=original.order_min,
            order_max=original.order_max, stop_loss=original.stop_loss,
            price_alert=original.price_alert,
            ladder_enabled=original.ladder_enabled, ladder=original.ladder,
            open_disabled=original.open_disabled, close_disabled=original.close_disabled,
        )
        self.add_card(new_card)
        return new_card

    def _save(self):
        data = {}
        valid_keys = TradingCard.__annotations__.keys()
        for cid, card in self._cards.items():
            data[cid] = {k: getattr(card, k) for k in valid_keys}
        card_store.save_cards(data)

    def load_from_storage(self):
        cards_dict = card_store.load_cards()
        valid_keys = TradingCard.__annotations__.keys()
        for card_id, card_data in cards_dict.items():
            try:
                filtered = {k: v for k, v in card_data.items() if k in valid_keys}
                self._cards[card_id] = TradingCard(**filtered)
            except Exception as e:
                logging.error(f"Failed to load card {card_id}: {e}")
        logging.info(f"Loaded {len(self._cards)} cards")

    # ── 仓位同步（REST）──────────────────────────────────

    async def sync_card(self, card_id: str, force_overwrite: bool = False, force_spot: bool = False):
        """REST 拉取仓位并更新单张卡片，然后广播"""
        card = self._cards.get(card_id)
        if not card: return

        # 绝对防御：无论何种触发途径（比如前端页面刷新、重启、修改参数、强制单击按钮），
        # 只要卡片处于暂停状态，彻底屏蔽实盘字典拉取，防止它被同币种的其他运行中的交易所持仓数量意外唤醒覆盖。
        if card.status != "running":
            logging.info(f"[SYNC BLOCKED] Card {card_id} ({card.symbol}) is {card.status}. Ignored.")
            return

        # 节流 0.5s
        now = time.time()
        if now - self._sync_throttle.get(card_id, 0) < 0.5:
            return
        self._sync_throttle[card_id] = now

        try:
            is_sf = card.type == "SF"
            map_a_task = self.exchange.fetch_all_positions_map(card.exchange_a, is_sf=is_sf)
            map_b_task = self.exchange.fetch_all_positions_map(card.exchange_b, is_sf=False)
            results = await asyncio.gather(map_a_task, map_b_task, return_exceptions=True)

            map_a = results[0] if not isinstance(results[0], Exception) else {}
            map_b = results[1] if not isinstance(results[1], Exception) else {}

            self._apply_position_data(card, map_a, map_b, force_overwrite=force_overwrite, force_spot=force_spot)
            self._save()
            await self._broadcast(card)

        except Exception as e:
            logging.error(f"[SYNC] Card {card_id} failed: {e}")

    async def sync_all_cards(self):
        """REST 批量同步所有 running 卡片"""
        running = [c for c in self._cards.values() if c.status == "running"]
        if not running: return

        req_start = time.time() * 1000

        # 并行拉取所有需要的仓位快照
        exs_lin = set()
        exs_spot = set()
        for c in running:
            if c.type == 'SF':
                exs_spot.add(c.exchange_a)
                exs_lin.add(c.exchange_b)
            else:
                exs_lin.add(c.exchange_a)
                exs_lin.add(c.exchange_b)

        tasks = []
        task_info = []

        for ex in exs_lin:
            tasks.append(self.exchange.fetch_all_positions_map(ex, is_sf=False))
            task_info.append((ex, False))
        for ex in exs_spot:
            tasks.append(self.exchange.fetch_all_positions_map(ex, is_sf=True))
            task_info.append((ex, True))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        lin_maps = {}
        spot_maps = {}
        
        for (ex, is_spot), res in zip(task_info, results):
            m = res if not isinstance(res, Exception) else {}
            if is_spot:
                spot_maps[ex] = m
            else:
                lin_maps[ex] = m

        for card in running:
            try:
                is_sf = card.type == "SF"

                # 根据 SF 类型和交易所正确选择现货/期货 map
                if is_sf:
                    map_a = spot_maps.get(card.exchange_a, {})
                else:
                    map_a = lin_maps.get(card.exchange_a, {})

                map_b = lin_maps.get(card.exchange_b, {})

                # 防止开仓后的旧数据覆盖
                if card.last_open_time > req_start:
                    continue

                self._apply_position_data(card, map_a, map_b)
                await self._broadcast(card)
            except Exception as e:
                logging.error(f"[BULK SYNC] {card.symbol} failed: {e}")

        self._save()

    def _apply_position_data(self, card: TradingCard, map_a: dict, map_b: dict, force_overwrite: bool = False, force_spot: bool = False):
        """从仓位数据解析并更新卡片。
        SF A 腿（现货）通常不从 Sync 拉数据，因为现货账户余额是全局共享的，无法区分各卡，只依赖内部记账。
        force_spot=True 时允许一次性覆写 SF A 腿，用于手动纠正账本漂移。
        FF 双腿均允许 Sync 更新。
        """
        is_sf = card.type == "SF"
        # force_spot=True 时，SF A腿也允许从实盘拉取（手动校准模式）
        treat_as_ff = not is_sf or force_spot
        target_a = 'long'
        target_b = 'short'

        # SF A腿（现货）通常维持内部记账值；force_spot=True 时允许从实盘拉取（强制校准模式）
        if treat_as_ff:
            pos_a = self.exchange.find_pos_list(map_a, card.symbol)
            qty_a, val_a, entry_a, pnl_a, liq_a, adl_a, mmr_a = self.exchange.parse_position_list(pos_a, card.symbol, target_side=target_a)
        else:
            qty_a, val_a, entry_a, pnl_a, liq_a, adl_a, mmr_a = card.position_qty_a or 0, card.position_value_a or 0, card.avg_price_a or 0, card.pnl_a or 0, card.liq_price_a or 0, card.adl_a or 0, card.margin_ratio_a or 0

        pos_b = self.exchange.find_pos_list(map_b, card.symbol)
        qty_b, val_b, entry_b, pnl_b, liq_b, adl_b, mmr_b = self.exchange.parse_position_list(pos_b, card.symbol, target_side=target_b)

        # A腿字段：treat_as_ff 时（FF 或 force_spot 校准模式）从实盘更新
        if treat_as_ff:
            card.position_qty_a = qty_a
            if entry_a > 0:
                card.avg_price_a = entry_a
            # 现货的 REST API 本身不含未实现盈亏，保护它不被置为 0
            if not is_sf or pnl_a != 0:
                card.pnl_a = pnl_a
            card.liq_price_a = liq_a
            card.adl_a = adl_a
            card.margin_ratio_a = mmr_a

        card.position_qty_b = qty_b
        if entry_b > 0:
            card.avg_price_b = entry_b
        card.pnl_b = pnl_b
        card.liq_price_b = liq_b
        card.adl_b = adl_b
        card.margin_ratio_b = mmr_b
        
        card.position_qty = max(card.position_qty_a or 0, qty_b)
        card.pnl = (card.pnl_a or 0) + pnl_b

        # B腿合约如果取不到 notional，用内存均价预估
        if val_b <= 0 and qty_b > 0:
            if card.avg_price_b > 0:
                val_b = qty_b * card.avg_price_b
            elif self.exchange._price_book:
                ex_b_key = "binance_future" if card.exchange_b == "binance" else f"{card.exchange_b}_linear"
                tk = self.exchange._price_book.get_ticker(card.symbol, ex_b_key)
                if tk:
                    bp = tk.get('lastPrice') or tk.get('ask') or tk.get('bid') or 0
                    if bp > 0:
                        val_b = qty_b * bp
                        card.avg_price_b = bp

        # A腿现货如果取不到 value（因为现货没有 notional），用最新市价（优先）或内存均价预估
        if treat_as_ff and val_a <= 0 and qty_a > 0:
            ap = 0
            if self.exchange._price_book:
                if card.exchange_a == "binance":
                    ex_a_key = "binance" if is_sf else "binance_future"
                else:
                    ex_a_key = f"{card.exchange_a}_spot" if is_sf else f"{card.exchange_a}_linear"
                tk = self.exchange._price_book.get_ticker(card.symbol, ex_a_key)
                if tk:
                    ap = tk.get('lastPrice') or tk.get('ask') or tk.get('bid') or 0
            
            # 现货的 avg_price_a 如果为 1.0 (通常是因为市价买入 U 数被当做币数记录产生 Bug)
            # 优先使用盘口市价；只有当拿不到盘口市价且均价正常时，才用均价兜底
            if ap <= 0 and card.avg_price_a > 0 and card.avg_price_a != 1.0:
                ap = card.avg_price_a
                
            if ap > 0:
                val_a = qty_a * ap
                # 修复市价买单由于返回 amount(USDT) 导致错误算出 avg_price=1.0 的数据残存
                if card.avg_price_a == 0 or card.avg_price_a == 1.0:
                    card.avg_price_a = ap

        # A腿 position_value：treat_as_ff 时允许覆写
        if treat_as_ff:
            if force_spot or val_a > 0 or qty_a == 0 or qty_a < 0.001:
                card.position_value_a = val_a
                if force_spot and qty_a < 0.001:
                    card.position_qty_a = 0  # 强制抹平粉尘

        # B腿：合约可区分，SF 和 FF 均允许 Sync 公正覆写
        if val_b > 0 or qty_b == 0:
            card.position_value_b = val_b

        # position_value 与两腿内存最大对齐
        ref_val = max(card.position_value_a or 0, card.position_value_b or 0)
        if treat_as_ff:
            card.position_value = ref_val
        else:
            if abs(ref_val - card.position_value) > 0.5:
                card.position_value = ref_val

        if force_spot:
            logging.warning(f"[CALIBRATE_APPLY] {card.symbol} qty_a={qty_a} val_a={val_a} -> card.qty_a={card.position_qty_a} card.val_a={card.position_value_a} card.val={card.position_value}")

    # ── WS 推送处理 ────────────────────────────────────

    async def on_ws_position_update(self, ex_key: str, updates: list):
        """处理 WS 实时仓位推送"""
        if not updates: return

        for card in self._cards.values():
            if card.status != "running": continue

            matched = False
            norm_sym = card.symbol.split(':')[0].replace('/', '')

            for pos in updates:
                event_sym = pos.get('symbol')
                event_side = pos.get('side', '').lower()
                qty = float(pos.get('qty', 0))
                price = float(pos.get('entry_price', 0))
                pnl = float(pos.get('pnl', 0))

                # A 侧匹配：只更新 qty 和均价，不写 position_value（全局量会污染多卡）
                if card.exchange_a in ex_key and norm_sym == event_sym:
                    target = "long"
                    if event_side and event_side != target: continue
                    card.position_qty_a = qty
                    if price > 0: card.avg_price_a = price
                    card.pnl_a = pnl
                    matched = True

                # B 侧匹配：只更新 qty 和均价，不写 position_value
                if card.exchange_b in ex_key and norm_sym == event_sym:
                    target = "short"
                    if event_side and event_side != target: continue
                    card.position_qty_b = qty
                    if price > 0: card.avg_price_b = price
                    card.pnl_b = pnl
                    matched = True

            if matched:
                card.position_qty = max(card.position_qty_a or 0, card.position_qty_b or 0)
                card.pnl = (card.pnl_a or 0) + (card.pnl_b or 0)
                await self._broadcast(card)

    async def on_execution_update(self, ex_key: str, executions: list):
        """处理成交推送 -> 触发 REST sync"""
        if not executions: return
        symbols = {e.get('symbol') for e in executions if e.get('symbol')}
        for sym in symbols:
            for card in self._cards.values():
                if card.status != "running": continue
                norm = card.symbol.split(':')[0].replace('/', '')
                if norm == sym and (card.exchange_a in ex_key or card.exchange_b in ex_key):
                    asyncio.create_task(self.sync_card(card.id))

    # ── 交易操作 ───────────────────────────────────────




    # ── 利润记录 ───────────────────────────────────────

    def _record_profit(self, card: TradingCard,
                       qty_a: float, entry_a: float, exit_a: float,
                       qty_b: float, entry_b: float, exit_b: float,
                       open_spread: float, close_spread: float):
        try:
            # 获取专门应对结算盈亏时的计量换算率
            def _get_cs(ex, t_type):
                if ('gate' not in ex and 'bitget' not in ex) or 'spot' in t_type: return 1.0
                try:
                    c = self.exchange.get_client(f"{ex}_{t_type}")
                    if c and hasattr(c, 'markets') and c.markets:
                        base = card.symbol[:-4] if card.symbol.endswith('USDT') else card.symbol
                        mkt = c.markets.get(f"{base}/USDT:USDT")
                        if mkt: return float(mkt.get('contractSize') or 1.0)
                except: pass
                return 1.0

            pnl_a, fee_a, rate_a = 0.0, 0.0, 0.0
            type_a = 'spot' if card.type == 'SF' else 'linear'
            term_a = "现货" if type_a == "spot" else "合约"
            
            # 将用于计算U盈亏的数量强行提纯为“标的币数”
            real_qty_a = qty_a * _get_cs(card.exchange_a, type_a)
            if real_qty_a > 0 and entry_a > 0 and exit_a > 0:
                pnl_a = (exit_a - entry_a) * real_qty_a if card.type != 'SF' else (exit_a - entry_a) * real_qty_a # (这里都是做空的A腿) 纠正：其实如果是对冲 arbitrage.py 里，无论 SF/FF ，A腿永远是 SHORT做空！但在上面如果把买卖弄混了？我们的套利逻辑A是做空的！做空的 profit应该等于 (entry - exit)
                
                # 如果是多空套利，A腿恒为 SHORT, B腿恒为 LONG！
                if card.type in ('FF', 'SF'):
                     pnl_a = (entry_a - exit_a) * real_qty_a

                rate_a = get_fee_rate(card.exchange_a, type_a)
                fee_a = abs(entry_a * real_qty_a * rate_a) + abs(exit_a * real_qty_a * rate_a)

            pnl_b, fee_b, rate_b = 0.0, 0.0, 0.0
            real_qty_b = qty_b * _get_cs(card.exchange_b, 'linear')
            if real_qty_b > 0 and entry_b > 0 and exit_b > 0:
                # B腿是 LONG
                pnl_b = (exit_b - entry_b) * real_qty_b
                rate_b = get_fee_rate(card.exchange_b, 'linear')
                fee_b = abs(entry_b * real_qty_b * rate_b) + abs(exit_b * real_qty_b * rate_b)

            total_pnl = (pnl_a + pnl_b) - (fee_a + fee_b)
            
            rmks = []
            if real_qty_a > 0:
                base_a = (entry_a * real_qty_a) + (exit_a * real_qty_a)
                rmks.append(f"A({card.exchange_a}{term_a}): [盈]{pnl_a:.3f}-[费率{(rate_a*100):.3f}%*逾{base_a:.0f}U本金]{fee_a:.3f}")
            if real_qty_b > 0:
                base_b = (entry_b * real_qty_b) + (exit_b * real_qty_b)
                rmks.append(f"B({card.exchange_b}合约): [盈]{pnl_b:.3f}-[费率{(rate_b*100):.3f}%*逾{base_b:.0f}U本金]{fee_b:.3f}")

            record = ProfitRecord(
                id=str(uuid.uuid4()), symbol=card.symbol, record_type="trade",
                strategy_type=card.type, exchange_a=card.exchange_a, exchange_b=card.exchange_b,
                pnl=total_pnl, fee=fee_a + fee_b, fee_a=fee_a, fee_b=fee_b,
                open_spread=open_spread, close_spread=close_spread,
                timestamp=int(time.time() * 1000), qty=(real_qty_a + real_qty_b) / 2,
                entry_price_a=entry_a, exit_price_a=exit_a,
                entry_price_b=entry_b, exit_price_b=exit_b,
                pnl_a=pnl_a, pnl_b=pnl_b,
                remarks=" | ".join(rmks)
            )
            profit_store.add_record(record)
            logging.info(f"[PROFIT] {card.symbol} pnl={total_pnl:.4f}")
        except Exception as e:
            logging.error(f"[PROFIT] Record failed: {e}")

    # ── 广播 ──────────────────────────────────────────

    async def _broadcast(self, card: TradingCard):
        if self._broadcast_cb:
            try:
                await self._broadcast_cb({
                    "type": "card_update",
                    "data": {"card": card.__dict__.copy()},
                })
            except Exception as e:
                logging.error(f"[BROADCAST] Failed: {e}")
