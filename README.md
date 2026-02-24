# BN-BY Project

## 项目结构

本项目包含 **两个独立的前端页面**，共用同一个 Next.js 服务：

| URL | 用途 | 文件路径 |
|-----|------|---------|
| `http://localhost:3000/` | **差价看板** (Arbitrage Dashboard) | `frontend/src/app/page.tsx` |
| `http://localhost:3000/trading` | **交易 UI** (Trading Dashboard) | `frontend/src/app/trading/page.tsx` |

---

## ⚠️ 重要提醒

> **修改交易 UI 时，只动 `frontend/src/app/trading/` 目录下的文件！**
> 
> **不要修改 `frontend/src/app/page.tsx`，那是差价看板的代码！**

---

## 启动服务

```bash
# Backend (端口 8000)
cd backend
py -m uvicorn backend.main:app --reload --port 8000

# Frontend (端口 3000)
cd frontend
npm run dev
```

## 目录说明

```
bn-by/
├── backend/                 # FastAPI 后端
│   ├── main.py             # 主入口
│   ├── trading/            # 交易相关
│   │   ├── base_trader.py
│   │   ├── binance_trader.py
│   │   └── bybit_trader.py
│   └── connectors/         # WebSocket 连接器
│
└── frontend/               # Next.js 前端
    └── src/app/
        ├── page.tsx        # 🔴 差价看板 (localhost:3000/)
        └── trading/        # 🟢 交易 UI (localhost:3000/trading)
            ├── page.tsx
            └── components/
                └── ExchangeTab.tsx
```
## 功能与修复说明



- **Bybit (拜比特)**:
  - 已支持 **统一交易账户 (UTA)**。
  - 自动处理余额查询时的账户类型参数（解决 `10001` 错误）。

### 2. Windows 兼容性
- 已解决 `aiodns` 在 Windows 上的事件循环冲突问题 (`SelectorEventLoop`)。
- 直接运行 `py start.py` 即可，无需修改环境。

## 常用命令

| 操作 | Windows (本地) | Linux (服务器) |
|------|---------------|----------------|
| **启动后端** | `py start.py` | `python3 backend/main.py` |
| **启动前端** | `npm run dev` | `npm run start` |
| **强制停止** | `taskkill /F /IM python.exe` | `pkill -f backend.main` |taskkill /F /IM node.exe
| **查看日志** | (控制台输出) | `tail -f backend.log` |

---
**注意**: 修改代码请务必关注 `backend/execution/executor.py` 中的 `_detect_binance_pm` 逻辑。



sudo kill -9 $(lsof -t -i:8000)