import requests
import json

API_BASE = "http://127.0.0.1:8000"

def test_update_card():
    # 1. Get list of cards
    try:
        res = requests.get(f"{API_BASE}/api/trading/cards")
        cards = res.json().get('cards', [])
        if not cards:
            print("No cards found.")
            return

        card = cards[0]
        card_id = card['id']
        print(f"Testing with card {card['symbol']} ({card_id})")
        print(f"Current Status: {card['status']}, Open Threshold: {card['open_threshold']}")

        # 2. Simulate "One Click Open" update
        # Payload similar to frontend
        payload = card.copy()
        payload['status'] = 'running'
        payload['open_threshold'] = -900.0
        payload['close_threshold'] = -999.0
        
        # Remove fields that might not be in request model or read-only if any (but backend uses same model)
        # Verify strict update
        
        print("\nSending PUT request...")
        res = requests.put(f"{API_BASE}/api/trading/card/{card_id}", json=payload)
        
        if res.status_code == 200:
            print("Update Response:", res.json())
        else:
            print("Update Failed:", res.text)
            return

        # 3. Verify update
        res = requests.get(f"{API_BASE}/api/trading/cards")
        updated_cards = res.json().get('cards', [])
        updated_card = next((c for c in updated_cards if c['id'] == card_id), None)
        
        if updated_card:
            print(f"\nUpdated Status: {updated_card['status']}")
            print(f"Updated Open Threshold: {updated_card['open_threshold']}")
            
            if updated_card['open_threshold'] == -900.0:
                 print("SUCCESS: Threshold updated correctly.")
            else:
                 print("FAILURE: Threshold did NOT update.")
        
        # 4. Restore (Optional)
        # payload['open_threshold'] = card['open_threshold']
        # requests.put(f"{API_BASE}/api/trading/card/{card_id}", json=payload)

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_update_card()
