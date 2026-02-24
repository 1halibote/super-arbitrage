import json
import sys

try:
    with open('backend/data/cards.json', 'r', encoding='utf-8') as f:
        cards = json.load(f)
        for _, c in cards.items():
            if c.get('type') == 'SF':
                print(f"Symbol: {c.get('symbol')}, Type: {c.get('type')}, ExA: {c.get('exchange_a')}, ExB: {c.get('exchange_b')}, Status: {c.get('status')}, OpenDisabled: {c.get('open_disabled')}, OpenSpread: {c.get('open_spread')}, OpenThreshold: {c.get('open_threshold')}, PNL: {c.get('pnl')}")
except Exception as e:
    print("Error:", e)
