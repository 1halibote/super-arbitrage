
import sys
import os
import time
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

from backend.execution.profit_store import ProfitStore, ProfitRecord

def verify():
    # 1. Initialize Store (Load real data)
    store = ProfitStore()
    
    print("--- 验证开始 ---")
    
    # 2. Get initial summary
    s1 = store.get_summary()
    print(f"初始今日利润: {s1['today_pnl']} U")
    print(f"初始当日资费: {s1['today_funding']} U")
    
    # 3. Create dummy funding record (-10 U)
    dummy_pnl = -10.0
    now_ts = int(time.time() * 1000)
    
    record = ProfitRecord(
        id="TEST_RECORD",
        symbol="BTCUSDT",
        record_type="funding",
        exchange_a="",
        exchange_b="binance",
        pnl=dummy_pnl,
        funding_rate=0.0001,
        funding_income_a=0,
        funding_income_b=dummy_pnl,
        external_id="TEST_REV_1",
        timestamp=now_ts
    )
    
    # 4. Inject into memory ONLY (Do not call add_record to avoid saving to disk)
    store._records.append(record)
    print(f"\n[操作] 注入一条测试记录: PNL = {dummy_pnl} U (类型: funding)")
    
    # 5. Get new summary
    s2 = store.get_summary()
    print(f"注入后今日利润: {s2['today_pnl']} U")
    print(f"注入后当日资费: {s2['today_funding']} U")
    
    # 6. Verify
    diff_pnl = s2['today_pnl'] - s1['today_pnl']
    diff_funding = s2['today_funding'] - s1['today_funding']
    
    print("\n--- 验证结果 ---")
    
    success = True
    if abs(diff_pnl - dummy_pnl) < 0.0001:
        print(f"✅ 今日利润正确扣除: {diff_pnl} (预期 {dummy_pnl})")
    else:
        print(f"❌ 今日利润计算错误: 变动 {diff_pnl}, 预期 {dummy_pnl}")
        success = False

    if abs(diff_funding - dummy_pnl) < 0.0001:
        print(f"✅ 当日资费正确累计: {diff_funding} (预期 {dummy_pnl})")
    else:
        print(f"❌ 当日资费计算错误: 变动 {diff_funding}, 预期 {dummy_pnl}")
        success = False
        
    return success

if __name__ == "__main__":
    verify()
