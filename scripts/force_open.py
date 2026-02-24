import urllib.request
import json

def force_open():
    url = 'http://localhost:8000/api/trading/cards'
    r = urllib.request.urlopen(url)
    cards = json.loads(r.read())
    
    target = None
    card_list = cards.values() if isinstance(cards, dict) else cards
    for c in card_list:
        if c.get('type') == 'SF' and c.get('exchange_a') == 'bybit':
            target = c
            break
            
    if not target:
        print("Card not found")
        return
        
    print(f"Old Thr: {target.get('open_threshold')} Qty: {target.get('position_value')}")
    target['open_threshold'] = -1.0  # Force open
    target['status'] = 'running'
    
    req = urllib.request.Request(f"{url}/{target['id']}", 
                                 data=json.dumps(target).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='PUT')
    res = urllib.request.urlopen(req)
    print("API Updated:", res.status)

if __name__ == '__main__':
    force_open()
