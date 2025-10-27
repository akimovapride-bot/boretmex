import os
import json
from typing import Dict, Any

STORAGE_DIR = os.path.join(os.getcwd(), "storage")
SETTINGS_PATH = os.path.join(STORAGE_DIR, "settings.json")

_DEFAULTS = {
    "signal_score": 0.68,
    "default_budget": 25.0,
    "watchlist": [],
}

def _ensure_dirs():
    if not os.path.isdir(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)

def load_settings() -> Dict[str, Any]:
    _ensure_dirs()
    if not os.path.isfile(SETTINGS_PATH):
        save_settings(_DEFAULTS.copy())
        return _DEFAULTS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # дополняем новыми ключами, если добавились
        for k, v in _DEFAULTS.items():
            data.setdefault(k, v)
        return data
    except Exception:
        # если файл битый — перезапишем дефолтом
        save_settings(_DEFAULTS.copy())
        return _DEFAULTS.copy()

def save_settings(data: Dict[str, Any]) -> None:
    _ensure_dirs()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
