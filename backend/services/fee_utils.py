
from typing import Dict

# Fee Structure (Standard Taker Rates)
# Users can customize these if they have VIP levels or BNB deductions later.
FEE_RATES = {
    "binance": {
        "spot": 0.001,      # 0.1%
        "linear": 0.0005,   # 0.05% (USDT-M Futures)
        "future": 0.0005,   # 0.05%
    },
    "bybit": {
        "spot": 0.001,      # 0.1%
        "linear": 0.00055,  # 0.055% (USDT Perpetual Taker)
        "future": 0.00055,  # 0.055%
    },
    "bitget": {
        "spot": 0.001,      # 0.1%
        "linear": 0.0006,   # 0.06%
        "future": 0.0006,   # 0.06%
    },
    "gate": {
        "spot": 0.001,      # 0.1%
        "linear": 0.0005,   # 0.05%
        "future": 0.0005,   # 0.05%
    }
}

DEFAULT_FEE = 0.0005

def get_fee_rate(exchange: str, market_type: str) -> float:
    """
    Get fee rate for an exchange and market type.
    :param exchange: 'binance' or 'bybit' (case insensitive)
    :param market_type: 'spot', 'linear' (future), or 'future'
    :return: Fee rate (float), e.g., 0.001 for 0.1%
    """
    ex_key = exchange.lower()
    m_key = market_type.lower()
    
    # Normalize market type
    if m_key == 'usdt': m_key = 'linear'
    if m_key == 'swap': m_key = 'linear'
    
    if ex_key in FEE_RATES:
        return FEE_RATES[ex_key].get(m_key, DEFAULT_FEE)
    return DEFAULT_FEE

def calculate_fee(qty: float, price: float, exchange: str, market_type: str) -> float:
    """Calculate absolute fee value"""
    rate = get_fee_rate(exchange, market_type)
    return abs(qty * price * rate)
