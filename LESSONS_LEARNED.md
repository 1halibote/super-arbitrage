# 问题解决总结与避坑指南 (LESSONS LEARNED)

## 目录
1. [Bybit Spot 价格相同问题](#1-bybit-spot-价格相同问题)
2. [币种缺失问题 (MEGA)](#2-币种缺失问题-mega)
3. [SS/FF 方向逻辑错误](#3-ssff-方向逻辑错误)
4. [Ticker 碰撞问题 (U)](#4-ticker-碰撞问题-u)
5. [Spot 交易量为0](#5-spot-交易量为0)

---

## 1. Bybit Spot 价格相同问题

### 问题描述
Bybit Spot 的 Bid 和 Ask 价格完全相同，没有价差。

### 根因分析
- 原来订阅的是 `tickers` 流
- `tickers` 流返回的 `lastPrice` 是最新成交价，不是 Bid/Ask
- 导致 Bid = Ask = LastPrice

### 解决方案
**正确做法**: 改用 `orderbook.1` 流
```python
# bybit.py 订阅逻辑
topic_prefix = "orderbook.1"  # 而不是 "tickers"
```

### 经验教训
- ✅ **正确**: WebSocket 流的选择需要根据实际需要的字段来决定
- ❌ **错误**: 假设所有流都包含 Bid/Ask

---

## 2. 币种缺失问题 (MEGA)

### 问题描述
用户报告 `MEGAUSDT` 在平台上存在，但系统没有显示。

### 根因分析
1. 首先检查了 API 返回列表 -> 发现 API 不包含 MEGA
2. 通过浏览器确认 Bybit 确实有 MEGA 交易对
3. **结论**: Bybit API `market/instruments` 有时会遗漏某些币种

### 解决方案
**Hotfix**: 在 connector 中手动注入缺失的币种
```python
# bybit.py _fetch_symbols()
# 强制添加已知遗漏的币种
if "MEGAUSDT" not in self.symbols:
    self.symbols.append("MEGAUSDT")
    logging.info("Forced MEGAUSDT into Linear symbols")
```

### 经验教训
- ✅ **正确**: 当 API 不可靠时，实现手动覆盖机制
- ❌ **错误**: 尝试用各种 headers/参数修复 API (浪费时间)
- ❌ **错误**: 写大量调试脚本 (`debug_mega.py`, `check_mega_requests.py`) 而不是直接 hotfix

---

## 3. SS/FF 方向逻辑错误

### 问题描述
SS 套利方向固定为 `Binance/Bybit`，FF 套利方向显示与实际多空不符。

### 根因分析
**SS问题**: 只计算了一个方向 (Buy Ex1, Sell Ex2)
**FF问题**: 后端按字母顺序传递 Ex1/Ex2，与前端 "多/空" 约定不匹配

### 解决方案
**SS**: 计算双向价差，两个方向都有利润时才显示
```python
# 方向1: Buy Ex1, Sell Ex2
opend = ((d2["bid"] - d1["ask"]) / d1["ask"]) * 100
# 方向2: Buy Ex2, Sell Ex1  
opend2 = ((d1["bid"] - d2["ask"]) / d2["ask"]) * 100
```

**FF**: 根据多空关系调整 Ex1/Ex2 顺序
```python
# Short Ex1, Long Ex2 -> 前端显示 Ex2(多) / Ex1(空)
"details": {"ex1": ex2, "ex2": ex1}  # 交换顺序
```

### 经验教训
- ✅ **正确**: 理解前端约定后再修改后端逻辑
- ❌ **错误**: 不看前端代码就假设后端逻辑正确

---

## 4. Ticker 碰撞问题 (U)

### 问题描述
`U` 币种显示 60,000% 的虚假价差。

### 根因分析
- Binance 的 `U` = "United Stables" (稳定币, ~$1.0)
- Bybit 的 `U` = 完全不同的代币 (价格极低)
- **Ticker 碰撞**: 同名不同币

### 解决方案
**黑名单机制**:
```python
class ArbitrageCalculator:
    BLACKLIST = {"UUSDT"}  # 已知异常币种
    
    def calculate_xx(self):
        for symbol in snapshot:
            if symbol in self.BLACKLIST: continue
```

### 经验教训
- ✅ **正确**: 实现黑名单机制处理已知异常
- ❌ **错误**: 花时间研究两个交易所的 U 是什么 (不影响解决方案)

---

## 5. Spot 交易量为0

### 问题描述
SF 和 SS 表格中，Spot 交易所的交易量显示为 $0。

### 根因分析
**Binance Spot**: 
- 订阅 `!ticker@arr` 流
- 包含 `q` (Quote Volume) 字段
- 但代码没有解析该字段

**Bybit Spot**:
- 之前只订阅 `orderbook.1` 流 (只有 Bid/Ask)
- `turnover24h` 在 `tickers` 流中

### 解决方案
**Binance**: 添加 volume 解析
```python
ticker = {
    ...
    "volume": float(item.get("q", 0)),  # 新增
}
```

**Bybit**: 同时订阅两种流
```python
# 订阅 orderbook 获取 Bid/Ask
args = [f"orderbook.1.{s}" for s in chunk]
# 同时订阅 tickers 获取 Volume
args = [f"tickers.{s}" for s in chunk]
```

### 经验教训
- ✅ **正确**: 先确认需要的数据字段在哪个流
- ❌ **错误**: 假设一个流包含所有需要的数据

---

## 通用避坑指南

### 1. 调试原则
- 使用浏览器验证交易所数据，不要只靠 API
- 先打 dump 文件确认收到的数据，再改逻辑
- 调试完成后**立即删除**调试代码和文件

### 2. 代码修改原则
- **先理解约定**: 前端/后端的数据格式约定
- **最小改动**: 一次只改一个地方，验证后再改下一个
- **不改已验证的代码**: 除非有明确 bug

### 3. 性能优化原则
- 限流: 后端广播间隔 >= 1.5s
- 分页: 前端显示 <= 50 条/页
- 紧凑协议: 用数组代替对象数组

### 4. 文档原则
- 每个 bug 记录: 问题 -> 根因 -> 方案 -> 经验
- 记录**错误的尝试**，避免重复踩坑

---

## 6. Binance PAPI Symbol 歧义问题

### 问题描述
在使用 Binance 统一账户 (PAPI) 客户端时，尝试下单或查询市场 `client.market('LAUSDT')` 抛出 `KeyError: 'papi'`。
错误堆栈指向 CCXT 内部，看起来像是 API 配置缺失，误导性极强。

### 根因分析
- **PAPI 客户端特性**: `ccxt.binance` 开启 `defaultType='papi'` 后，会加载**所有**市场类型（现货、合约、期权等）。
- **Symbol 歧义**: Raw Symbol（如 `LAUSDT`）在全市场上下文中不够明确，CCXT 内部路由尝试解析时，无法将其唯一映射到 Linear 合约，导致查找内部配置时失败（KeyError）。
- **误导性**: 之前使用的 `binanceusdm` 客户端只加载合约市场，所以 `LAUSDT` 能正常工作。这让我们误以为是 API Key 问题。

### 解决方案
**强制使用 CCXT Unified Symbol**:
在 PAPI 客户端中，必须使用精确的统一格式符号来消除歧义：
- Linear Futures: `LA/USDT:USDT`
- Spot: `LA/USDT`

```python
# executor.py
if s.endswith('USDT') and '/' not in s:
    unified_symbol = f"{s[:-4]}/USDT:USDT"
market = client.market(unified_symbol)  # ✅ Success
```

### 经验教训
- ✅ **正确**: 在 Unified Account (PAPI) 环境下，永远使用 Unified Symbol (`BASE/QUOTE:SETTLE`)。
- ❌ **错误**: 假设 Raw Symbol (`BASEQUOTE`) 在所有客户端通吃。
- ❌ **错误**: 看到 `KeyError: 'papi'` 就认为是 URL 配置问题（可能是 Symbol 解析导致的副作用）。

