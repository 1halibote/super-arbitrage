import asyncio
import json
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.execution.exchange_client import ExchangeClient
from backend.execution.card_manager import CardManager

class DummyCard:
    def __init__(self):
        self.id = "test_sync_card"
        self.symbol = "AZTECUSDT"
        self.status = "running"
        self.type = "FF"
        self.exchange_a = "gate"
        self.exchange_b = "bybit"
        self.position_qty_a = 20.0
        self.position_value_a = 20.0
        self.position_qty_b = 20.0
        self.position_value_b = 20.0
        self.position_value = 20.0
        self.last_open_time = 0
        self.avg_price_a = 0
        self.avg_price_b = 0
        self.pnl_a = 0
        self.pnl_b = 0
        self.liq_price_a = 0
        self.liq_price_b = 0
        self.adl_a = 0
        self.adl_b = 0
        self.margin_ratio_a = 0
        self.margin_ratio_b = 0

logging.basicConfig(level=logging.INFO)

class DummyWS:
    async def broadcast_card(self, c): pass
    
async def test():
    ec = ExchangeClient()
    await ec.initialize()
    cm = CardManager(ec)
    
    card = DummyCard()
    cm._cards[card.id] = card
    
    print("--- Before Sync ---")
    print(f"Card A: qty={card.position_qty_a} val={card.position_value_a}")
    print(f"Card B: qty={card.position_qty_b} val={card.position_value_b}")
    print(f"Card Total: {card.position_value}")
    
    # Enable verbose debug mode to trace exactly where it goes wrong
    print("\n--- Running sync_all_cards ---")
    await cm.sync_all_cards()
    
    print("\n--- After Sync ---")
    print(f"Card A: qty={card.position_qty_a} val={card.position_value_a}")
    print(f"Card B: qty={card.position_qty_b} val={card.position_value_b}")
    print(f"Card Total: {card.position_value}")

asyncio.run(test())
