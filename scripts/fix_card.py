import urllib.request
import json

def fix():
    url = 'http://localhost:8000/api/trading/cards'
    r = urllib.request.urlopen(url)
    cards = json.loads(r.read())
    
    target = None
    for c in cards:
        if c.get('type') == 'SF' and c.get('exchange_a') == 'bybit':
            target = c
            break
            
    if not target:
        print("Card not found")
        return
        
    print(f"Before: threshold={target.get('open_threshold')} qty={target.get('position_value')}")
    target['open_threshold'] = -0.015
    target['position_value'] = 0.0
    target['position_qty_a'] = 0.0
    target['position_qty_b'] = 0.0
    
    req = urllib.request.Request(f"{url}/{target['id']}", 
                                 data=json.dumps(target).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='PUT')
    res = urllib.request.urlopen(req)
    print("Update status:", res.status)

if __name__ == '__main__':
    fix()
