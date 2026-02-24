"""
交易卡片持久化存储
使用 JSON 文件保存卡片配置
"""
import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import asdict

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "cards.json")

class CardStore:
    """卡片存储管理器"""
    
    def __init__(self):
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(DATA_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def save_cards(self, cards: Dict) -> bool:
        """保存所有卡片到文件"""
        try:
            # 将 TradingCard 对象转换为 dict
            cards_dict = {}
            for card_id, card in cards.items():
                if hasattr(card, '__dict__'):
                    cards_dict[card_id] = card.__dict__.copy()
                else:
                    cards_dict[card_id] = card
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(cards_dict, f, indent=2, ensure_ascii=False)
            logging.debug(f"Saved {len(cards_dict)} cards to {DATA_FILE}")
            return True
        except Exception as e:
            logging.error(f"Failed to save cards: {e}")
            return False
    
    def load_cards(self) -> Dict:
        """从文件加载所有卡片"""
        if not os.path.exists(DATA_FILE):
            return {}
        
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                cards_dict = json.load(f)
            logging.info(f"Loaded {len(cards_dict)} cards from {DATA_FILE}")
            return cards_dict
        except Exception as e:
            logging.error(f"Failed to load cards: {e}")
            return {}
    
    def delete_card(self, card_id: str) -> bool:
        """删除单个卡片"""
        cards = self.load_cards()
        if card_id in cards:
            del cards[card_id]
            return self._save_raw(cards)
        return False
    
    def _save_raw(self, cards_dict: Dict) -> bool:
        """直接保存字典"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(cards_dict, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Failed to save cards: {e}")
            return False

# 全局实例
card_store = CardStore()
