
# 常见问题与解决方案 (Troubleshooting)

## 1. 后端启动报错 (Windows)
**现象**：`NotImplementedError` regarding `ProactorEventLoop` and `aiodns`.  
**原因**：`aiohttp` 依赖的 `aiodns` 在 Windows 上默认使用 Proactor 事件循环时存在兼容性问题。  
**解决方案**：  
在 `backend/run.py` 和主要脚本入口中，强制设置事件循环策略为 `WindowsSelectorEventLoopPolicy`。
```python
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

## 2. API Key 保存无反应 / 列表为空
**现象**：前端点击保存没反应，或刷新后列表为空。  
**原因**：
1.  `executor.initialize()` 中 `load_markets()` 因网络原因卡死，导致后端 hang 住。
2.  `load_markets` 在旧代码中是同步阻塞的。
**解决方案**：
*   后端增加了 `timeout` 设置。
*   `load_markets` 改为异步且在后台运行，防止阻塞主启动流程。

## 3. Bybit 余额显示异常 (0 或不全)
**现象**：Bybit 交易所可交易，但持仓概览中余额显示为 0 或只显示部分。  
**原因**：  
Bybit **统一账户 (Unified Account)** 的资产结构与普通账户不同。普通解析逻辑只检查 `bal['total']`，而统一账户的某些资产（如 USDT）可能隐藏在币种详情 `bal['USDT']['total']` 中，或需要通过特定参数获取。  
**解决方案**：  
更新了 `executor.py` 中的资产解析逻辑，采用“全字段扫描”策略，并针对 Bybit 统一账户做了特殊处理（如果合约资产为空但现货有钱，自动镜像显示，因为统一账户资金是共享的）。

## 4. Binance 合约余额为 0 (Portfolio Margin 账户)
**现象**：Binance 现货显示正常，但合约余额一直为 0。  
**原因**：  
用户使用的是 **Binance 统一账户 (Portfolio Margin / PM)**。标准合约接口 (`fapi`) 对 PM 用户受限（报错 `-2015 IP/Perms`），必须使用专门的 **PAPI** 接口。  
**解决方案**：  
在 `executor.py` 中实现了智能回退机制。默认尝试标准接口，如果失败则自动切换到 `papi` 接口读取余额。
