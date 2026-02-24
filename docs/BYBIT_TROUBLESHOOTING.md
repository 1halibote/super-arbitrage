# Bybit 数据流排坑指南

> 本文档记录了 Bybit 接入过程中遇到的坑点及解决方案，供日后维护参考。

---

## 🔥 核心坑点 #1：V5 Spot Tickers 不包含 bid/ask

### 问题表现
- FF 看板有数据（Bybit Linear 正常）
- SS 看板始终为空（Bybit Spot 无数据）
- Debug 接口显示 `bybit_spot` 符号数正确，但 bid/ask 均为 `MISSING`

### 根本原因
**Bybit V5 Spot tickers WebSocket 消息中 `不包含` bid/ask 字段！**

对比两种消息格式：

#### Linear Tickers（正常）
```json
{
  "topic": "tickers.BTCUSDT",
  "data": {
    "symbol": "BTCUSDT",
    "lastPrice": "66666.60",
    "bid1Price": "66666.60",  // ✅ 有 bid
    "ask1Price": "66666.70",  // ✅ 有 ask
    "fundingRate": "-0.005",
    "volume24h": "73191.3870"
  }
}
```

#### Spot Tickers（**无 bid/ask！**）
```json
{
  "topic": "tickers.BTCUSDT",
  "data": {
    "symbol": "BTCUSDT",
    "lastPrice": "21109.77",
    "volume24h": "6780.866843",
    "turnover24h": "141946527.22907118",
    "price24hPcnt": "0.0196",
    "usdIndexPrice": "21120.24"
    // ❌ 没有 bid1Price / ask1Price
  }
}
```

### 解决方案
**Spot 必须订阅 `orderbook.1.{symbol}` 来获取 bid/ask：**

```python
# 错误做法（Spot 无法获取 bid/ask）
args = [f"tickers.{s}" for s in chunk]

# 正确做法
if self.category == "linear":
    args = [f"tickers.{s}" for s in chunk]  # Linear 用 tickers
else:
    args = [f"orderbook.1.{s}" for s in chunk]  # Spot 用 orderbook.1
```

Orderbook 响应格式：
```json
{
  "topic": "orderbook.1.BTCUSDT",
  "data": {
    "s": "BTCUSDT",
    "b": [["66666.60", "1.234"]],  // bid
    "a": [["66666.70", "5.678"]]   // ask
  }
}
```

---

## 🔥 核心坑点 #2：Bybit 启动慢（600+ 符号）

### 问题表现
- 系统刚启动时 FF/SS 看板为空
- 20-30 秒后数据才开始出现

### 根本原因
Bybit 有 **559+ 个 Linear 符号** 和 **476+ 个 Spot 符号**，比 Binance 多得多。

每 10 个符号一批订阅，每批间隔 0.3 秒，总共需要约 30-50 秒完成订阅。

### 解决方案
- 启动脚本中增加等待时间（`timeout /t 20`）
- 前端显示 "数据同步中..." 提示
- 不要在启动后立刻判定"无数据"

---

## 🔥 核心坑点 #3：重启后数据消失

### 问题表现
- 手动停止再启动后，数据需要重新同步
- 有时候 WebSocket 连接失败需要重试

### 根本原因
- Python uvicorn `--reload` 模式导致代码修改时自动重启
- Bybit WebSocket 连接需要重新建立和订阅

### 解决方案
- 生产环境关闭 `--reload` 模式
- 使用 `start_all.bat` / `stop_all.bat` 一键脚本管理
- 连接失败时自动重试（代码已实现）

---

## 📋 快速诊断清单

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| SS 全空，FF 正常 | Spot 订阅格式错误（用了 tickers） | 改用 `orderbook.1.{symbol}` |
| FF 全空，SS 正常 | Linear 订阅格式错误 | 检查 tickers 订阅 |
| 全部为空 | 后端未启动或网络问题 | 检查 8000 端口和网络 |
| 数据时有时无 | WebSocket 断线重连 | 检查后端日志 |
| 启动后 30 秒内无数据 | 订阅未完成 | 正常现象，耐心等待 |

---

## 🛠️ 调试命令

```powershell
# 检查 PriceBook 中各交易所符号数
Invoke-WebRequest -Uri "http://localhost:8000/api/debug/book" -UseBasicParsing | Select -Exp Content

# 检查 Bybit Spot 的实际数据（bid/ask 是否有值）
Invoke-WebRequest -Uri "http://localhost:8000/api/debug/spot" -UseBasicParsing | Select -Exp Content

# 检查 FF/SS/SF 数量
$json = (Invoke-WebRequest -Uri "http://localhost:8000/api/snapshot").Content | ConvertFrom-Json
Write-Host "FF: $($json.ff.Count), SS: $($json.ss.Count), SF: $($json.sf.Count)"
```

---

## ✅ 最终完美方案 (2026-02-06 13:45)

### 核心矛盾
- 订阅 `tickers`: 有 Volume，无 Bid/Ask ❌
- 订阅 `orderbook`: 有 Bid/Ask，无 Volume ❌

### 方案：双订阅策略 🚀
同时订阅 `orderbook.1` 和 `tickers`，各取所需。

#### 1. 后端修复
- **文件**: `backend/connectors/bybit.py`
- **逻辑**: Spot 订阅时，request args 同时包含 `orderbook.1.{s}` 和 `tickers.{s}`。
- **优化**: 将 Spot 的 `chunk_size` 从 10 降为 5，避免双倍订阅量触发限制。

```python
# 伪代码
args = []
for s in chunk:
    args.append(f"orderbook.1.{s}")
    args.append(f"tickers.{s}")
```

#### 2. 前端复原
- **文件**: `frontend/src/app/page.tsx`
- **逻辑**: 恢复 `minVolume` 过滤器。因为后端现在能提供正确的 volume，所以不需要前端 hack。

### 验证
- Bid/Ask: ✅ 正常 (来自 orderbook)
- Volume: ✅ 正常 (来自 tickers，不再是 0)
- SS 看板: ✅ 完整显示且支持过滤
