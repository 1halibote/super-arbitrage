import json
import os
from datetime import datetime

fp = 'backend/data/profit_records.json'
out_fp = 'debug_profits.txt'
if not os.path.exists(fp):
    with open(out_fp, 'w', encoding='utf-8') as f:
        f.write("No profit records found.")
else:
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data = sorted(data, key=lambda x: x.get('timestamp', 0), reverse=True)
    with open(out_fp, 'w', encoding='utf-8') as f:
        f.write("--- Latest 5 Profit Records ---\n")
        for r in data[:5]:
            f.write("-------------\n")
            f.write(f"ID: {r.get('id')}\n")
            f.write(f"Time: {datetime.fromtimestamp(r.get('timestamp', 0)/1000)}\n")
            f.write(f"Symbol: {r.get('symbol')}\n")
            f.write(f"Total PNL: {r.get('pnl')}\n")
            f.write(f"Fee A: {r.get('fee_a')} | Fee B: {r.get('fee_b')}\n")
            f.write(f"PNL A: {r.get('pnl_a')} | PNL B: {r.get('pnl_b')}\n")
            f.write(f"Entry A: {r.get('entry_price_a')} | Exit A: {r.get('exit_price_a')}\n")
            f.write(f"Entry B: {r.get('entry_price_b')} | Exit B: {r.get('exit_price_b')}\n")
            f.write(f"Qty Avg: {r.get('qty')}\n")
            remarks = r.get('remarks', '').replace('\n', ' ').replace('\r', '')
            f.write(f"Remarks: {remarks}\n")
