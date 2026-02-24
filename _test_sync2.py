import asyncio
import uuid
from backend.execution.models import TradingCard
from backend.execution.card_manager import CardManager

class MockExchange:
    def find_pos_list(self, pos_map, sym):
        return []
    def parse_position_list(self, pos_map, sym, target_side="both"):
        # return qty_a, val_a, entry_a, pnl_a, liq_a, adl_a, mmr_a
        return 10.0, 100.0, 10.0, 5.0, 0.0, 0, 0.0
    async def fetch_all_positions_map(self, ex, is_sf):
        return {"TEST": []}
    
class MockStore:
    def load_cards(self): return {}
    def save_cards(self, cards): pass

cm = CardManager(MockStore(), MockExchange())

async def run():
    card1 = TradingCard(id="C1", symbol="TEST", status="running", type="FF")
    card2 = TradingCard(id="C2", symbol="TEST", status="paused", type="FF")
    cm.add_card(card1)
    cm.add_card(card2)
    
    print(f"C1={cm.get_card('C1').position_qty}, C2={cm.get_card('C2').position_qty}")
    
    await cm.sync_card("C1", force_overwrite=True)
    
    print(f"C1={cm.get_card('C1').position_qty}, C2={cm.get_card('C2').position_qty}")

asyncio.run(run())
