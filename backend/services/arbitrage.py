from typing import List, Dict
import logging

class ArbitrageCalculator:
    # Blacklist for known anomalies or ticker collisions
    BLACKLIST = {"UUSDT"}

    def __init__(self, price_book):
        self.book = price_book

    async def _calc_common(self, type: str, raw_results: List[dict]):
        # Removed. Doing explicit loops for clarity as before.
        pass

    def calculate_all(self):
        """汇总所有计算结果 (SF + FF)"""
        try:
            sf = self.calculate_sf()
        except: sf = []
        try:
            ff = self.calculate_ff()
        except: ff = []
        
        results = {}
        for item in sf + ff:
            sym = item.get('symbol')
            pair = item.get('pair')
            if sym and pair:
                if sym not in results: results[sym] = {}
                results[sym][pair] = item
        return results

    def calculate_sf(self) -> List[dict]:
        results = []
        snapshot = self.book.get_snapshot()

        for symbol, exchanges in snapshot.items():
            if symbol in self.BLACKLIST: continue
            
            # [Optimization] Filter spots/futures once
            # Pre-allocate for speed
            spots = []
            futures = []
            
            for ex_name, data in exchanges.items():
                # Fast string checks
                if "spot" in ex_name or ex_name == "binance":
                     if "future" not in ex_name and "linear" not in ex_name:
                         spots.append((ex_name, data))
                         continue # Exclusive
                
                if "future" in ex_name or "linear" in ex_name:
                    futures.append((ex_name, data))
            
            for s_name, s_data in spots:
                for f_name, f_data in futures:
                    if not self._valid(s_data) or not self._valid(f_data): continue

                    bid_s, ask_s = s_data["bid"], s_data["ask"]
                    bid_f, ask_f = f_data["bid"], f_data["ask"]
                    
                    # Funding & Interval
                    fr_s, int_s = 0, ""
                    fr_f, int_f = f_data.get("fundingRate", 0) * 100, self._get_interval(f_data)
                    
                    # SF Spread Logic (Pulse Algorithm)
                    # Open: Long Spot (Ex1), Short Future (Ex2) -> (Bid_F - Ask_S) / Ask_S
                    # Close: Short Spot (Ex1), Long Future (Ex2) -> (Ask_F - Bid_S) / Bid_S
                    
                    if ask_s > 0:
                        open_diff_1 = ((bid_f - ask_s) / ask_s) * 100
                    else:
                        open_diff_1 = 0
                        
                    if bid_s > 0:
                        close_diff_1 = ((ask_f - bid_s) / bid_s) * 100
                    else:
                        close_diff_1 = 0
                    
                    # Index Spread
                    idx_s = s_data.get("indexPrice", 0)
                    idx_f = f_data.get("indexPrice", 0)
                    mk_f = f_data.get("markPrice", 0)
                    
                    # Spot: Diff = 0 (No Mark/Index relationship distinct from Price)
                    idx_diff_s = 0
                    
                    # Future: Diff = (Mark - Index) / Index
                    idx_diff_f = 0
                    if idx_f > 0 and mk_f > 0:
                        idx_diff_f = (mk_f - idx_f) / idx_f * 100
                        
                    # Volume Split (Sum removed, passing individual)
                    vol_s = s_data.get("volume", 0)
                    vol_f = f_data.get("volume", 0)
                    vol_sum = vol_s + vol_f

                    # Limits (Restored)
                    f_max, f_min = f_data.get("fundingMax", 0) * 100, f_data.get("fundingMin", 0) * 100
                    
                    # Rounding (Restored)
                    fr_f = round(fr_f, 3)
                    if fr_s != 0: fr_s = round(fr_s * 100, 3)

                    results.append({
                        "symbol": symbol,
                        "type": "SF",
                        "pair": f"{s_name}/{f_name}",
                        "openSpread": open_diff_1,
                        "closeSpread": close_diff_1,
                        "fundingRateA": fr_s,
                        "fundingIntervalA": int_s,
                        "fundingRateB": fr_f,
                        "fundingIntervalB": int_f,
                        "fundingMaxB": f_max,
                        "fundingMinB": f_min,
                        "netFundingRate": fr_f - fr_s,
                        "indexDiffA": idx_diff_s,
                        "indexDiffB": idx_diff_f,
                        "indexPriceA": idx_s,
                        "indexPriceB": idx_f,
                        "volume": vol_sum,
                        "volumeA": vol_s,
                        "volumeB": vol_f,
                        "bidA": bid_s, "askA": ask_s,
                        "bidB": bid_f, "askB": ask_f,
                        "details": {
                            "ex1": s_name, "ex1_price": ask_s,
                            "ex2": f_name, "ex2_price": bid_f
                        }
                    })

        results.sort(key=lambda x: abs(x["openSpread"]), reverse=True)
        return results

    def calculate_ff(self) -> List[dict]:
        results = []
        snapshot = self.book.get_snapshot()

        for symbol, exchanges in snapshot.items():
            if symbol in self.BLACKLIST: continue
            
            futures = []
            for ex_name, data in exchanges.items():
                if "future" in ex_name or "linear" in ex_name:
                    futures.append((ex_name, data))
            
            for i in range(len(futures)):
                for j in range(i+1, len(futures)):
                    ex1, d1 = futures[i]
                    ex2, d2 = futures[j]
                    if not self._valid(d1) or not self._valid(d2): continue

                    fr1, int1 = d1.get("fundingRate", 0) * 100, self._get_interval(d1)
                    fr2, int2 = d2.get("fundingRate", 0) * 100, self._get_interval(d2)
                    
                    # Limits
                    fr1_max, fr1_min = d1.get("fundingMax", 0) * 100, d1.get("fundingMin", 0) * 100
                    fr2_max, fr2_min = d2.get("fundingMax", 0) * 100, d2.get("fundingMin", 0) * 100
                    
                    # Index
                    idx1 = d1.get("indexPrice", 0)
                    idx2 = d2.get("indexPrice", 0)
                    # Index Diff Calculation
                    # Diff = (Mark - Index) / Index * 100
                    def get_idx_diff(d):
                        mk = d.get("markPrice", 0)
                        idx = d.get("indexPrice", 0)
                        if mk > 0 and idx > 0:
                            return (mk - idx) / idx * 100
                        return 0
                        
                    idx1_diff = get_idx_diff(d1)
                    idx2_diff = get_idx_diff(d2)
                    
                    if symbol == "BIRBUSDT":
                         # Debug Print
                         pass
                         # logging.info(f"FF CALC: {ex1}/{ex2} -> Spreads calculated. Validating...")

                    vol1 = d1.get("volume", 0)
                    vol2 = d2.get("volume", 0)
                    vol_sum = vol1 + vol2

                    # Precision Fix: Round to 3 decimals matching UI to ensure A-B=C visual consistency
                    # But using 4 internal to minimize drift, no user wants 3.
                    # User complaint: "Some accurate, some off by 0.001".
                    # If I use 3 decimals here, it will MATCH the UI exactly.
                    # If I use 4, it might still deviate.
                    # Let's use 3 decimals (0.001%) as that's the display format.
                    fr1 = round(fr1, 3)
                    fr2 = round(fr2, 3)

                    # 1. Short Ex1, Long Ex2
                    # Ex1 is Short (Bottom), Ex2 is Long (Top) -> Display Ex2/Ex1
                    opend = (2 * (d1["bid"] - d2["ask"]) / (d1["bid"] + d2["ask"])) * 100
                    closed = (2 * (d1["ask"] - d2["bid"]) / (d1["ask"] + d2["bid"])) * 100
                    
                    # Filter: If BOTH are negative, skip
                    results.append({
                        "symbol": symbol, "type": "FF", "pair": f"{ex2}/{ex1}",
                        "openSpread": opend, "closeSpread": closed,
                        "fundingRateA": fr2, "fundingIntervalA": int2, # Top (Long) -> Ex2
                        "fundingRateB": fr1, "fundingIntervalB": int1, # Bot (Short) -> Ex1
                        "fundingMaxA": fr2_max, "fundingMinA": fr2_min,
                        "fundingMaxB": fr1_max, "fundingMinB": fr1_min,
                        "netFundingRate": fr1 - fr2, # Receive fr1 - Pay fr2
                        "indexDiffA": idx2_diff, # Top
                        "indexDiffB": idx1_diff, # Bot
                        "indexPriceA": d2.get("indexPrice", 0),
                        "indexPriceB": d1.get("indexPrice", 0),
                        "volume": vol_sum, "volumeA": vol2, "volumeB": vol1, # Top=Ex2, Bot=Ex1
                        "bidA": d2["bid"], "askA": d2["ask"],
                        "bidB": d1["bid"], "askB": d1["ask"],
                        "details": {"ex1": ex2, "ex2": ex1} # ex1=Top(Long), ex2=Bot(Short)
                    })

                    # 2. Long Ex1, Short Ex2
                    # Ex1 is Long (Top), Ex2 is Short (Bottom) -> Display Ex1/Ex2
                    opend2 = (2 * (d2["bid"] - d1["ask"]) / (d2["bid"] + d1["ask"])) * 100
                    closed2 = (2 * (d2["ask"] - d1["bid"]) / (d2["ask"] + d1["bid"])) * 100
                    
                    results.append({
                        "symbol": symbol, "type": "FF", "pair": f"{ex1}/{ex2}",
                        "openSpread": opend2, "closeSpread": closed2,
                        "fundingRateA": fr1, "fundingIntervalA": int1, # Top (Long) -> Ex1
                        "fundingRateB": fr2, "fundingIntervalB": int2, # Bot (Short) -> Ex2
                        "fundingMaxA": fr1_max, "fundingMinA": fr1_min,
                        "fundingMaxB": fr2_max, "fundingMinB": fr2_min,
                        "netFundingRate": fr2 - fr1, # Receive fr2 - Pay fr1
                        "indexDiffA": idx1_diff, # Top
                        "indexDiffB": idx2_diff, # Bot
                        "indexPriceA": d1.get("indexPrice", 0),
                        "indexPriceB": d2.get("indexPrice", 0),
                        "volume": vol_sum, "volumeA": vol1, "volumeB": vol2,
                        "bidA": d1["bid"], "askA": d1["ask"],
                        "bidB": d2["bid"], "askB": d2["ask"],
                        "details": {"ex1": ex1, "ex2": ex2}
                    })
        
        results.sort(key=lambda x: abs(x["openSpread"]), reverse=True)
        return results

    def calculate_ss(self) -> List[dict]:
        # Similar logic for SS, but 0 funding, 0 index usually
        results = []
        snapshot = self.book.get_snapshot()
        for symbol, exchanges in snapshot.items():
            if symbol in self.BLACKLIST: continue
            spots = []
            for ex_name, data in exchanges.items():
                if "future" not in ex_name and "linear" not in ex_name:
                    spots.append((ex_name, data))
            
            # Sort spots alphabetically: 'binance' < 'bybit_spot'
            spots.sort(key=lambda x: x[0])
            
            for i in range(len(spots)):
                for j in range(i+1, len(spots)):
                    ex1, d1 = spots[i]
                    ex2, d2 = spots[j]
                    if not self._valid(d1) or not self._valid(d2): continue
                    
                    vol1 = d1.get("volume", 0)
                    vol2 = d2.get("volume", 0)
                    vol_sum = vol1 + vol2
                    
                    # 1. Buy Ex1, Sell Ex2 (Long Ex1, Short Ex2)
                    # Profit if Sell Ex2 (Bid) > Buy Ex1 (Ask)
                    if d1["ask"] > 0 and d2["bid"] > 0:
                        opend = ((d2["bid"] - d1["ask"]) / d1["ask"]) * 100
                        closed = ((d2["ask"] - d1["bid"]) / d1["bid"]) * 100
                        
                        # Relaxed filter to show near-zero opportunities (monitor mode)
                        if opend > -1.0:
                            results.append({
                                "symbol": symbol, "type": "SS", "pair": f"{ex1}/{ex2}",
                                "openSpread": opend, "closeSpread": closed,
                                "fundingRateA": 0, "fundingIntervalA": "",
                                "fundingRateB": 0, "fundingIntervalB": "",
                                "netFundingRate": 0,
                                "indexSpread": 0,
                                "volume": vol_sum, "volumeA": vol1, "volumeB": vol2,
                                "details": {"ex1": ex1, "ex2": ex2} # Ex1 is Long (Top), Ex2 is Short (Bot)
                            })

                    # 2. Buy Ex2, Sell Ex1 (Long Ex2, Short Ex1)
                    # Profit if Sell Ex1 (Bid) > Buy Ex2 (Ask)
                    if d2["ask"] > 0 and d1["bid"] > 0:
                        opend2 = ((d1["bid"] - d2["ask"]) / d2["ask"]) * 100
                        closed2 = ((d1["ask"] - d2["bid"]) / d2["bid"]) * 100
                        
                        if opend2 > -1.0:
                            results.append({
                                "symbol": symbol, "type": "SS", "pair": f"{ex2}/{ex1}",
                                "openSpread": opend2, "closeSpread": closed2,
                                "fundingRateA": 0, "fundingIntervalA": "",
                                "fundingRateB": 0, "fundingIntervalB": "",
                                "netFundingRate": 0,
                                "indexSpread": 0,
                                "volume": vol_sum, "volumeA": vol2, "volumeB": vol1,
                                "details": {"ex1": ex2, "ex2": ex1} # Ex2 is Long (Top), Ex1 is Short (Bot)
                            })
        
        results.sort(key=lambda x: abs(x["openSpread"]), reverse=True)
        return results

    def calculate_prices(self) -> List[dict]:
        """
        提取所有交易对的原始报价，用于前端价格对比 (Price Monitor)
        """
        results = []
        snapshot = self.book.get_snapshot()
        
        for symbol, exchanges in snapshot.items():
            if not symbol.endswith("USDT"):
                continue

            row = {
                "symbol": symbol,
                "binance_spot": {"bid": 0, "ask": 0, "last": 0},
                "binance_future": {"bid": 0, "ask": 0, "last": 0},
                "bybit_spot": {"bid": 0, "ask": 0, "last": 0},
                "bybit_future": {"bid": 0, "ask": 0, "last": 0},
                "bitget_spot": {"bid": 0, "ask": 0, "last": 0},
                "bitget_future": {"bid": 0, "ask": 0, "last": 0},
                "gate_spot": {"bid": 0, "ask": 0, "last": 0},
                "gate_future": {"bid": 0, "ask": 0, "last": 0},
                "nado_spot": {"bid": 0, "ask": 0, "last": 0},
                "nado_future": {"bid": 0, "ask": 0, "last": 0},
                "lighter_spot": {"bid": 0, "ask": 0, "last": 0},
                "lighter_future": {"bid": 0, "ask": 0, "last": 0},
            }
            
            for ex_name, data in exchanges.items():
                price_data = {
                    "bid": data.get("bid", 0), 
                    "ask": data.get("ask", 0), 
                    "last": data.get("lastPrice", 0)
                }
                
                if ex_name == "binance":
                    row["binance_spot"] = price_data
                elif ex_name == "binance_future":
                    row["binance_future"] = price_data
                elif ex_name == "bybit_spot":
                    row["bybit_spot"] = price_data
                elif ex_name == "bybit_linear":
                    row["bybit_future"] = price_data
                elif ex_name == "bitget_spot":
                    row["bitget_spot"] = price_data
                elif ex_name == "bitget_linear":
                    row["bitget_future"] = price_data
                elif ex_name == "gate_spot":
                    row["gate_spot"] = price_data
                elif ex_name == "gate_linear":
                    row["gate_future"] = price_data
                elif ex_name == "nado_spot":
                    row["nado_spot"] = price_data
                elif ex_name == "nado_linear":
                    row["nado_future"] = price_data
                elif ex_name == "lighter_spot":
                    row["lighter_spot"] = price_data
                elif ex_name == "lighter_linear":
                    row["lighter_future"] = price_data
            
            has_binance = row["binance_spot"]["bid"] > 0 or row["binance_future"]["bid"] > 0
            has_bybit = row["bybit_spot"]["bid"] > 0 or row["bybit_future"]["bid"] > 0
            has_bitget = row["bitget_spot"]["bid"] > 0 or row["bitget_future"]["bid"] > 0
            has_gate = row["gate_spot"]["bid"] > 0 or row["gate_future"]["bid"] > 0
            has_nado = row["nado_spot"]["bid"] > 0 or row["nado_future"]["bid"] > 0
            has_lighter = row["lighter_spot"]["bid"] > 0 or row["lighter_future"]["bid"] > 0
            
            exchange_count = sum([has_binance, has_bybit, has_bitget, has_gate, has_nado, has_lighter])
            if symbol.endswith("USDT") and exchange_count >= 1:
                results.append(row)
                
        results.sort(key=lambda x: x["symbol"])
        return results

    def _valid(self, data):
        return data.get("bid", 0) > 0 and data.get("ask", 0) > 0

    def _get_interval(self, data):
        # 1. Prefer static interval from Exchange Info (e.g. 8, 4, 1)
        if "fundingInterval" in data:
            return int(data["fundingInterval"])
            
        # 2. Fallback: Calculate from timestamp
        nxt = data.get("nextFundingTime", 0)
        if nxt == 0: return 8 # Default to 8h
        
        # Heuristic: If remaining time > 4h, it's 8h.
        import time
        now = time.time() * 1000
        diff = nxt - now
        hours_remaining = diff / (1000 * 3600)
        
        if hours_remaining > 4.1: return 8
        if hours_remaining > 1.1: return 4
        return 8 # Default safest
