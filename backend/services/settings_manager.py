import json
import os
from pydantic import BaseModel
from typing import List, Dict

SETTINGS_FILE = "settings.json"

class ExchangeConfig(BaseModel):
    spot: bool = True
    contract: bool = True

class AppSettings(BaseModel):
    minVolume24h: float = 0
    exactSearch: bool = False
    exchanges: Dict[str, ExchangeConfig] = {
        "binance": ExchangeConfig(),
        "bybit": ExchangeConfig(),
        # Add others as placeholders if needed, but logic only for bn/by
    }
    blockedCoins: List[str] = []
    renamedCoins: Dict[str, str] = {}

class SettingsManager:
    def __init__(self):
        self.settings = AppSettings()
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings = AppSettings(**data)
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                f.write(self.settings.model_dump_json(indent=4))
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def get_settings(self) -> AppSettings:
        return self.settings

    def update_settings(self, new_settings: dict) -> AppSettings:
        self.settings = AppSettings(**new_settings)
        self.save()
        return self.settings

# Global instance
settings_manager = SettingsManager()
