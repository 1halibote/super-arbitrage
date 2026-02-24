# Latency & UX Optimization Tasks

- [x] **Backend Optimization**
    - [x] `monitor.py`: Implement "Instant Feedback" (emit event before execution). <!-- id: 0 -->
    - [x] Phase 9: Full Flow Analysis (Current)
    - [x] Monitor Code Cleanup (Removed unused imports/comments)
    - [x] Critical Fix: Implement missing `finalize_trade_session` in Executor
    - [x] Documentation Generation
- [x] Phase 10: Position Imbalance Fix (Quantity Neutrality)
    - [x] Create `verify_qty_recalc.py` for logic simulation
    - [x] Refactor `execute_arbitrage` in `executor.py` to use shared quantity
    - [x] Verify fix with simulation and dry-run
    - [x] `executor.py`: Verify `list_cards` is O(1) memory access. <!-- id: 1 -->
- [x] **Frontend Optimization**
    - [x] `TradingPage.tsx`: Add visual cue for "Processing" state (Amber/Loading). <!-- id: 2 -->
- [x] **Safety Verification**
    - [x] Verify `rate_limit` logic covers all execution paths to prevent IP bans. <!-- id: 3 -->
