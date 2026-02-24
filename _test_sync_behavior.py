import asyncio
import uuid
import time
from backend.execution.models import TradingCard
from backend.execution.card_manager import card_manager
from backend.execution.exchange_client import exchange_client
from backend.key_store import api_key_store

async def test_sync():
    api_key_store.load_from_storage()
    await exchange_client.initialize()
    
    card1 = TradingCard(
        id=str(uuid.uuid4())[:8],
        symbol="MYXUSDT",
        type="FF",
        exchange_a="binance",
        exchange_b="binance",
        status="running"
    )
    card2 = TradingCard(
        id=str(uuid.uuid4())[:8],
        symbol="MYXUSDT",
        type="FF",
        exchange_a="binance",
        exchange_b="binance",
        status="paused"
    )
    card_manager.add_card(card1)
    card_manager.add_card(card2)
    
    print(f"Before sync:")
    print(f"Card 1 (running): qty={card1.position_qty}")
    print(f"Card 2 (paused) : qty={card2.position_qty}")
    
    print("Syncing card 1...")
    await card_manager.sync_card(card1.id, force_overwrite=True)
    
    print(f"After sync Card 1:")
    print(f"Card 1 (running): qty={card1.position_qty}")
    print(f"Card 2 (paused) : qty={card2.position_qty}")
    
    # Clean up
    card_manager.remove_card(card1.id)
    card_manager.remove_card(card2.id)

asyncio.run(test_sync())
