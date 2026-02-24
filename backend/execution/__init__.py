"""
Trading 模块
"""
from .key_store import api_key_store
from .models import TradingCard, OrderResult, ExecutionResult, ExecutionStatus
from .exchange_client import exchange_client
from .card_manager import CardManager
from .position_ws import position_ws

# 创建 card_manager（依赖 exchange_client）
card_manager = CardManager(exchange_client)

# 延迟创建 monitor（依赖 card_manager 和 exchange_client）
# monitor 在 main.py startup 时初始化
from .monitor import TradingMonitor
trading_monitor = TradingMonitor(card_manager, exchange_client)

__all__ = [
    "api_key_store",
    "exchange_client", "card_manager",
    "TradingCard", "OrderResult", "ExecutionResult", "ExecutionStatus",
    "trading_monitor",
    "position_ws",
]
