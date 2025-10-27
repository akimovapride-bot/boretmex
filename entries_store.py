import json
import os
from threading import RLock

_LOCK = RLock()
_PATH = "entries.json"

def load_entries():
    with _LOCK:
        if not os.path.exists(_PATH):
            return {}
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

def save_entries(d: dict):
    with _LOCK:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

def set_entry(symbol: str, price: float):
    symbol = symbol.upper()
    d = load_entries()
    d[symbol] = float(price)
    save_entries(d)

def get_entry(symbol: str):
    symbol = symbol.upper()
    return load_entries().get(symbol)
