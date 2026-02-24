# IMPL: Fix Position Imbalance (Delta Neutrality)

## Problem
Current logic calculates order quantity based on USDT value independently for each leg:
```python
amount_a = qty_usdt / price_a
amount_b = qty_usdt / price_b
```
Due to the price spread, `amount_a` != `amount_b` (e.g., Long 1.0 SOL, Short 0.99 SOL).
This creates a "net position" exposure. When prices move, the PnL of the extra coins is not hedged, leading to value drift and imbalance over time.

## Solution
Change to **Quantity Neutral** logic:
1.  Calculate a target Coin Quantity based on the `qty_usdt` and the *average* price (or conservative price).
2.  Normalize this quantity to match the *stricter* (coarser) precision of the two exchanges.
    *   If Bybit allows 0.001 SOL and Binance allows 0.01 SOL, we must trade in multiples of 0.01 SOL.
3.  Use the exact same Coin Quantity for both orders.

## Proposed Changes

### `backend/execution/executor.py`

#### `execute_arbitrage`
- **Steps**:
    1.  Get `price_a` and `price_b`.
    2.  Calculate `target_qty = qty_usdt / avg(price_a, price_b)`.
    3.  Fetch `lot_size` (step size) for both markets.
    4.  Determine `common_step_size = max(step_size_a, step_size_b)`.
    5.  Round `target_qty` down to nearest `common_step_size`.
    6.  Set `amount_a = target_qty`, `amount_b = target_qty`.

#### `verify_qty_recalc.py` (New Script)
- Simulate the new logic with various inputs to prove correction.

## Verification Plan

### Automated Test
Run `py verify_qty_recalc.py` to confirm logic handles:
- Different prices (Spread)
- Different precisions (e.g., 0.1 vs 0.01)
- Min Notional limits (ensure result > min)

### User Review
- The user can see the output of the simulation.
