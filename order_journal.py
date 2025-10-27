import json, os, time
from typing import Dict, Any, List

STORAGE_DIR = "storage"
ORDERS_PATH = os.path.join(STORAGE_DIR, "orders.json")

def _ensure():
    if not os.path.isdir(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.isfile(ORDERS_PATH):
        with open(ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

def log_order(entry: Dict[str, Any]) -> None:
    _ensure()
    entry = dict(entry)
    entry.setdefault("ts", int(time.time()*1000))
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        arr = json.load(f)
    arr.append(entry)
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)

def list_orders(limit: int = 20) -> List[Dict[str, Any]]:
    _ensure()
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return arr[-limit:]
