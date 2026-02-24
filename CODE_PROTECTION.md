# 核心代码保护指南 (CODE PROTECTION)

> ⚠️ **警告**: 以下代码区域包含核心业务逻辑，已经过验证。**未经允许，严禁修改！**

## 1. 交易量采集 (Fixed 2026-02-04)
### `backend/connectors/bybit.py`
- **Spot逻辑**: 必须**同时**订阅 `orderbook.1` 和 `tickers`。
- **原因**: `orderbook` 只有买卖盘，`tickers` 才有 `turnover24h`。

### `backend/connectors/binance.py`
- **Spot解析**: 必须解析 `item.get("q", 0)`。
- **原因**: 这是一个隐藏字段，默认不解析会导致 Spot 交易量为 0。

## 2. 异常币种过滤 (Fixed 2026-02-04)
### `backend/services/arbitrage.py`
- **黑名单**: `BLACKLIST = {"UUSDT"}`
- **原因**: Ticker Collision (Binance United Stables vs Bybit Unknown U).

## 3. 套利方向逻辑 (Fixed 2026-02-04)
### `backend/services/arbitrage.py`
- **SS**: **双向计算** (Buy A/Sell B AND Buy B/Sell A)。
- **FF**: **反转显示** (如果 Short Ex1/Long Ex2，必须返回 `pair: Ex2/Ex1`)。
- **原因**: 前端强制约定 Top=Long, Bot=Short。

---
**如何安全的修改?**
1. 运行 `git status` 确保工作区干净。
2. 运行 `git checkout -b new-feature` 创建新分支。
3. 修改代码。
4. 验证失败? 运行 `git checkout .` 瞬间回滚。
