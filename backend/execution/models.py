"""
数据模型定义
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ExecutionStatus(Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class OrderResult:
    order_id: str = ""
    status: str = ""
    filled_qty: float = 0
    avg_price: float = 0
    cost: float = 0
    success: bool = False
    error: str = ""


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    order_a: Optional[OrderResult] = None
    order_b: Optional[OrderResult] = None
    total_latency_ms: float = 0
    error: str = ""


@dataclass
class TradingCard:
    """交易卡片"""
    id: str
    symbol: str
    status: str = "paused"
    type: str = "SF"
    exchange_a: str = "binance"
    exchange_b: str = "bybit"
    leverage: int = 1

    # 开清仓阈值
    open_threshold: float = 1.0
    close_threshold: float = 0.0
    max_position: float = 1000
    order_min: float = 8
    order_max: float = 10

    # 阶梯
    ladder_enabled: bool = False
    ladder: List[Dict] = field(default_factory=list)

    open_disabled: bool = False
    close_disabled: bool = False

    stop_loss: float = 0
    price_alert: float = 0
    start_time: int = 0

    # 仓位 - 总量
    position_qty: float = 0
    position_value: float = 0
    avg_price: float = 0
    pnl: float = 0

    # 仓位 - A 所
    avg_price_a: float = 0
    position_qty_a: float = 0
    position_value_a: float = 0
    pnl_a: float = 0

    # 仓位 - B 所
    avg_price_b: float = 0
    position_qty_b: float = 0
    position_value_b: float = 0
    pnl_b: float = 0

    # 差价记录
    open_spread: float = 0
    close_spread: float = 0
    last_open_time: int = 0
    last_close_time: int = 0

    # 风险
    liq_price_a: float = 0
    liq_price_b: float = 0
    adl_a: int = 0
    adl_b: int = 0
    margin_ratio_a: float = 0
    margin_ratio_b: float = 0
