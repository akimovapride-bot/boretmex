import json
import os
import time

STORAGE_DIR = "storage"
ORDERS_PATH = os.path.join(STORAGE_DIR, "orders.json")

def _ensure():
    if not os.path.isdir(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.isfile(ORDERS_PATH):
        with open(ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

def add_order_record(record: dict):
    _ensure()
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        arr = json.load(f)
    record["ts"] = int(time.time() * 1000)
    arr.append(record)
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(arr[-1000:], f, ensure_ascii=False, separators=(",", ":"))

def load_orders() -> list[dict]:
    _ensure()
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
