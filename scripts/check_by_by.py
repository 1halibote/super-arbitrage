import json
cards = json.load(open('backend/data/cards.json', encoding='utf-8'))
for c in cards.values():
    if c['type'] == 'SF' and c['exchange_a'] == 'bybit' and c['exchange_b'] == 'bybit':
        print(f"Status: {c['status']}, Thresh: {c['open_threshold']}, Spread: {c['open_spread']}, Qty: {c['position_value']}")
