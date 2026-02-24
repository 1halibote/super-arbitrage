# 全链路交易流程分析报告 (Full Trading Flow Analysis)

## 1. 系统架构总览
本系统采用 **React Frontend + FastAPI Backend** 架构，核心交易逻辑由后端 Python 引擎驱动。
- **前端**: 负责数据显示、用户交互、手动指令下发。通过 WebSocket 接收实时推送。
- **后端**: 
  - `Monitor`: 负责高频轮询 (10ms)、状态监控、自动触发。
  - `Executor`: 负责订单执行、CCXT/PAPI 交互、资金费率/仓位同步。
  - `Calculator`:负责实时差价计算。

---

## 2. 自动交易链路 (Auto Trading Flow)

### 2.1 触发机制
1.  **监控循环 (`monitor.py` -> `_monitor_loop`)**:
    -   以 **10ms** 间隔运行。
    -   遍历所有 `status="running"` 的 `TradingCard`。
    -   **并发控制**: 每个 Card 最多允许 10 个并发任务 (`semaphore`)，防止 API 洪水。

2.  **条件检查**:
    -   获取 `Calculator` 计算的实时 `Spread`。
    -   **开仓条件**: `spread >= open_threshold`
    -   **平仓条件**: `spread <= close_threshold`
    -   **风控检查**:
        -   `max_position` (最大持仓限制)
        -   `Time Lock` (开仓后冷却、清仓后 10s 冷却)
        -   `Burst Fire` (瞬间突发批量下单，填充并发池)

### 2.2 执行逻辑 (`executor.py`)
1.  **下单执行 (`execute_arbitrage`)**:
    -   **Binance PM 优化**: 自动检测是否为统一账户，如果是则切换至 `PAPI` (Portfolio API) 模式，使用 `um/order` 原生接口，绕过 CCXT Spot 路由问题。
    -   **杠杆设置**: 带有缓存 (`_leverage_cache`) 和 1s 超时，避免每次下单重复请求。
    -   **数量计算**: 严格检查 `min_notional` (如 Binance > 5U)。
    -   **并发执行**: A/B 两个交易所的订单通过 `asyncio.gather` 并行发送。

2.  **状态更新 (Optimistic Update)**:
    -   **关键机制**: 在收到交易所回报前，**立即**在内存中更新 `TradingCard` 的 `position_value`。
    -   **目的**: 防止 Monitor 下一次 10ms 循环时看到旧仓位而重复触发下单 (Double Spending)。
    -   **最终一致性**: 后台会有 `_safe_sync` (10s 周期) 从交易所拉取真实仓位进行校准。

### 2.3 核心实现细节 (Implementation Details)
#### A. 开仓 (Open)
- **入口**: `monitor.py` -> `_trigger_open` -> `executor.execute_arbitrage(is_close=False)`
- **方向**: 
  - **SF (无风险套利)**: 买入 Spot (A) + 卖出 Future (B)
  - **FF (跨期套利)**: 买入低价 Future (A) + 卖出高价 Future (B)
- **并发**: 使用 `asyncio.gather` 同时发送 A/B 两侧订单，尽可能减少 Leg Risk (单腿成交风险)。

#### B. 平仓 (Close)
- **入口**: `monitor.py` -> `_trigger_close` -> `executor.execute_arbitrage(is_close=True)`
- **方向**: 反向操作 (卖出 A + 买入 B)。
- **参数**: 强制设置 `reduceOnly=True` (仅减仓)，防止因延迟或重试导致的意外反向开仓。
- **批量算法 (Batching)**: 
  - 当持仓量 (`position_value`) > `order_max` 时，Monitor 会自动将大单拆分为多个小单 (Chunks)。
  - **并发执行**: 一次性发射 5-10 个小单 (Chunk) 并行成交，以突破 API 频率限制并减少滑点。
  - **异常处理**: 如果某个 Chunk 失败 (如 MinNotional 不足)，自动跳过并重试剩余部分。

#### C. 价差计算公式 (Spread Calculation)
位于 `arbitrage.py`，基于 Orderbook Snapshot 计算：
- **SF Spread**: `(Bid_Future - Ask_Spot) / Ask_Spot * 100%` (开仓: 空期货/多现货)
- **FF Spread**: `(Bid_FutureB - Ask_FutureA) / Ask_FutureA * 100%` (开仓: 空B/多A)
- **平仓 Spread**: 使用反向价格 (`Ask_Future - Bid_Spot`) 计算，确保覆盖 Bid/Ask Spread 成本。

---

## 3. 手动交易链路 (Manual Trading Flow)

### 3.1 手动开仓 (Manual Open)
**路径**: Frontend -> Backend -> Monitor (Auto)
前端的 "一键开仓" **并没有** 调用独立的开仓接口，而是巧妙复用了自动交易链路：

1.  **前端动作 (`page.tsx` -> `handleExecute`)**:
    -   用户点击 "开仓"。
    -   发送 `PUT /api/trading/card/{id}`。
    -   **Payload**: 将 `open_threshold` 设为 **-900%**，`close_threshold` 设为 **-999%**，`status` 设为 **"running"**。
2.  **后端响应**:
    -   更新数据库和内存中的 Card 配置。
3.  **触发执行**:
    -   `Monitor` 下一次循环检测到 `-900%` 的阈值（必然满足当前差价）。
    -   立即触发标准 `_trigger_open` 流程。
    -   **优势**: 复用了所有自动交易的风控（最大持仓、并发限制、余额检查），无需维护两套代码。

### 3.2 手动平仓 (Manual Close)
**路径**: Frontend -> Backend API -> Executor
手动平仓逻辑较为特殊，分为 "强制平仓" 和 "卡片接管"：

1.  **前端动作 (`page.tsx` -> `handleClose`)**:
    -   **若卡片暂停中**: 
        -   先弹窗确认。
        -   发送 `PUT` 更新卡片为 `running` 且设置安全阈值 (`open=999`, `close=900`)，防止误开仓。
    -   **执行请求**: 发送 `POST /api/trading/force-close/{symbol}`。

2.  **后端执行 (`executor.py` -> `force_close_all`)**:
    -   **不依赖本地状态**: 直接调用 Exchange API 拉取当前真实持仓 (`fetch_positions` / `PAPI account`)。
    -   **执行平仓**: 对持有仓位发送反向市价单。
    -   **广播**: 平仓完成后，广播最新的 Card 状态给前端。

---

## 4. 前端显示与交互 (Frontend)

### 4.1 状态同步
-   **WebSocket (`useTradingStream`)**:
    -   监听 `/ws/trading` 频道。
    -   接收 `card_update` 事件。
    -   **音频反馈**: 收到更新时，计算仓位变化 (`diff`)，如果变化显著则播放音效 (Ding/Dong)。
-   **兜底轮询**:
    -   每 5秒 调用 `/api/trading/cards` 全量刷新，防止 WebSocket 丢包导致状态由于 UI 永久卡死。

### 4.2 视觉反馈
-   **报警机制 (`page.tsx` -> `alarmTimerRef`)**:
    -   **条件**: (单腿持仓 OR 严重不平衡) AND (非 Syncing 状态) AND (持续 8秒)。
    -   **效果**: 卡片变红，播放警报音 (Sawtooth Wave)。
-   **交互**:
    -   拖拽排序 (Drag & Drop)。
    -   置顶功能 (Pin)。

---

## 5. 总结
-   **设计哲学**: "所见即所得，自动即手动"。手动开仓仅仅是"由于条件变得极其容易满足"的自动开仓。
-   **安全性**: 
    -   **内存锁**: 防止高频并发下的超额开仓。
    -   **UI Lock**: Sync 期间锁定 UI 更新，防止数值跳变。
    -   **PAPI 优先**: 针对 Binance 统一账户做了深度优化。
