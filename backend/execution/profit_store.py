"""
利润记录存储模块
记录平仓利润和资金费率结算，支持按日/月/累计聚合
"""

import json
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROFIT_FILE = os.path.join(DATA_DIR, "profit_records.json")


@dataclass
class ProfitRecord:
    id: str                   # 唯一标识
    symbol: str               # 交易对
    record_type: str          # 'trade' 平仓 | 'funding' 资金费率
    exchange_a: str           # A 所
    exchange_b: str           # B 所
    pnl: float                # 已实现盈亏 (含手续费)
    strategy_type: str = "SF" # 'SF' (Spot-Future) | 'FF' (Future-Future)
    fee: float = 0.0          # 手续费 (总)
    fee_a: float = 0.0        # A 手续费
    fee_b: float = 0.0        # B 手续费
    open_spread: float = 0.0  # 开仓价差
    close_spread: float = 0.0 # 平仓价差
    timestamp: int = 0        # 毫秒时间戳
    # 平仓明细
    qty: float = 0.0
    entry_price_a: float = 0.0
    exit_price_a: float = 0.0
    entry_price_b: float = 0.0
    exit_price_b: float = 0.0
    pnl_a: float = 0.0       # A 所已实现 PNL
    pnl_b: float = 0.0       # B 所已实现 PNL
    hold_duration: int = 0   # 持仓时长 (ms)
    # 资金费率明细
    funding_rate: float = 0.0
    funding_income_a: float = 0.0
    funding_income_b: float = 0.0
    external_id: str = ""     # 外部交易ID (用于去重)
    remarks: str = ""         # 附加结算公式及备注

class ProfitStore:
    def __init__(self):
        self._records: List[ProfitRecord] = []
        self._load()

    def _load(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if os.path.exists(PROFIT_FILE):
                with open(PROFIT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._records = [ProfitRecord(**r) for r in data]
                logging.info(f"[PROFIT] 加载 {len(self._records)} 条利润记录")
        except Exception as e:
            logging.error(f"[PROFIT] 加载失败: {e}")
            self._records = []

    def _save(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PROFIT_FILE, 'w', encoding='utf-8') as f:
                json.dump([asdict(r) for r in self._records], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"[PROFIT] 保存失败: {e}")

    def add_record(self, record: ProfitRecord):
        if not record.timestamp:
            record.timestamp = int(time.time() * 1000)
        self._records.append(record)
        self._save()
        logging.info(f"[PROFIT] 新增记录: {record.symbol} type={record.record_type} pnl={record.pnl:.4f}")

    def has_external_id(self, external_id: str) -> bool:
        if not external_id:
            return False
        return any(getattr(r, 'external_id', '') == external_id for r in self._records)

    def get_records(self, limit: int = 50, offset: int = 0, symbol: str = None) -> List[dict]:
        filtered = self._records
        if symbol:
            filtered = [r for r in filtered if r.symbol == symbol]
        # 按时间降序
        filtered = sorted(filtered, key=lambda r: r.timestamp, reverse=True)
        return [asdict(r) for r in filtered[offset:offset + limit]]

    def get_summary(self) -> dict:
        # Use UTC+8 for China Standard Time
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        today_ts = int(today_start.timestamp() * 1000)
        month_ts = int(month_start.timestamp() * 1000)

        today_pnl = 0.0
        month_pnl = 0.0
        total_pnl = 0.0
        
        today_trades = 0
        month_trades = 0
        total_trades = 0
        
        today_funding = 0.0
        month_funding = 0.0
        total_funding = 0.0

        today_hold_ms = 0
        month_hold_ms = 0
        total_hold_ms = 0

        for r in self._records:
            total_pnl += r.pnl
            
            if r.record_type == 'trade':
                total_trades += 1
                total_hold_ms += getattr(r, 'hold_duration', 0)
                
                if r.timestamp >= month_ts:
                    month_trades += 1
                    month_hold_ms += getattr(r, 'hold_duration', 0)
                    month_pnl += r.pnl # PNL only from trades or both? Let's check original. Original added all PNL.
                
                if r.timestamp >= today_ts:
                    today_trades += 1
                    today_hold_ms += getattr(r, 'hold_duration', 0)
                    today_pnl += r.pnl

            # Correcting logic: Original code added PNL for funding too. 
            # If record_type == 'funding', it also contributes to PNL.
            if r.record_type == 'funding':
                total_funding += r.pnl
                total_pnl += r.pnl # Wait, loop continues below? No, need to be careful.
                # Original loop:
                # total_pnl += r.pnl
                # total_trades += 1 (Wait, funding counts as trade in original? Yes, "total_trades += 1" was unconditional)
                # Let's align with original behavior but refine "trades" count if needed.
                # Actually, "trades" usually implies closed positions. Funding is an event.
                # The user wants "Average Closing Time", which implies holding time of TRADES.
                
                if r.timestamp >= month_ts:
                    month_funding += r.pnl
                    month_pnl += r.pnl
                if r.timestamp >= today_ts:
                    today_funding += r.pnl
                    today_pnl += r.pnl
            
        # Re-calculating to ensure clean logic based on previous file content
        # Previous content:
        # for r in self._records:
        #     total_pnl += r.pnl
        #     total_trades += 1 ...
        
        # Let's do a clean pass:
        today_pnl = 0.0
        month_pnl = 0.0
        total_pnl = 0.0
        
        today_trades = 0
        month_trades = 0
        total_trades = 0
        
        today_funding = 0.0
        month_funding = 0.0
        total_funding = 0.0
        
        today_hold_ms = 0
        month_hold_ms = 0
        total_hold_ms = 0
        
        real_trades_total = 0
        real_trades_month = 0
        real_trades_today = 0

        for r in self._records:
            total_pnl += r.pnl
            total_trades += 1 # Keeps compatible with existing "trades" count which seemingly included everything
            
            if r.record_type == 'funding':
                total_funding += r.pnl
                if r.timestamp >= month_ts:
                    month_funding += r.pnl
                if r.timestamp >= today_ts:
                    today_funding += r.pnl

            if r.record_type == 'trade':
                real_trades_total += 1
                total_hold_ms += getattr(r, 'hold_duration', 0)
                if r.timestamp >= month_ts:
                    real_trades_month += 1
                    month_hold_ms += getattr(r, 'hold_duration', 0)
                if r.timestamp >= today_ts:
                    real_trades_today += 1
                    today_hold_ms += getattr(r, 'hold_duration', 0)
            
            if r.timestamp >= month_ts:
                month_pnl += r.pnl
                month_trades += 1
            if r.timestamp >= today_ts:
                today_pnl += r.pnl
                today_trades += 1

        return {
            'today_pnl': round(today_pnl, 4),
            'month_pnl': round(month_pnl, 4),
            'total_pnl': round(total_pnl, 4),
            'today_trades': today_trades,
            'month_trades': month_trades,
            'total_trades': total_trades,
            'today_funding': round(today_funding, 4),
            'month_funding': round(month_funding, 4),
            'total_funding': round(total_funding, 4),
            'today_avg_hold': int(today_hold_ms / real_trades_today) if real_trades_today > 0 else 0,
            'month_avg_hold': int(month_hold_ms / real_trades_month) if real_trades_month > 0 else 0,
            'total_avg_hold': int(total_hold_ms / real_trades_total) if real_trades_total > 0 else 0,
        }

    def get_daily_stats(self, date_str: str) -> dict:
        try:
            # Parse date (Format: YYYY-MM-DD)
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Define time range in UTC+8
            tz = timezone(timedelta(hours=8))
            
            # Start of day
            start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
            # End of day (Start of next day)
            end_dt = start_dt + timedelta(days=1)
            
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
            
            pnl = 0.0
            trades = 0
            funding = 0.0
            hold_ms = 0
            real_trades = 0
            
            filtered_records = []
            
            for r in self._records:
                if start_ts <= r.timestamp < end_ts:
                    filtered_records.append(asdict(r))
                    pnl += r.pnl
                    
                    if r.record_type == 'trade':
                        trades += 1 # Total count logic
                        real_trades += 1
                        hold_ms += getattr(r, 'hold_duration', 0)
                    
                    if r.record_type == 'funding':
                        funding += r.pnl
                        trades += 1 # Consistent with get_summary logic
            
            avg_hold = int(hold_ms / real_trades) if real_trades > 0 else 0
            
            return {
                "date": date_str,
                "pnl": round(pnl, 4),
                "trades": trades,
                "funding": round(funding, 4),
                "avg_hold": avg_hold,
                "records": filtered_records # Also return records for that day? User might want to see table too.
            }
        except Exception as e:
            logging.error(f"get_daily_stats error: {e}")
            return {}

# 全局实例
profit_store = ProfitStore()
