import os
import json
import time
from typing import Dict, Any, List, Tuple, Optional

from mexc_client import get_my_trades

DATA_DIR = os.path.join("data")
MANUAL_FILE = os.path.join(DATA_DIR, "avg_entries_manual.json")
AUTO_FILE = os.path.join(DATA_DIR, "avg_entries_auto.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===== Ручные оверрайды =====
def load_manual_entries() -> Dict[str, float]:
    raw = _load_json(MANUAL_FILE)
    return {k.upper(): float(v) for k, v in raw.items()}


def set_manual_entry(symbol: str, price: float) -> None:
    data = load_manual_entries()
    data[symbol.upper()] = float(price)
    _save_json(MANUAL_FILE, data)


# ===== Авторасчёт из сделок =====
def load_auto_entries() -> Dict[str, Any]:
    return _load_json(AUTO_FILE)


def save_auto_entries(data: Dict[str, Any]) -> None:
    _save_json(AUTO_FILE, data)


def _calc_avg_from_trades(trades: List[Dict[str, Any]]) -> Tuple[Optional[float], float]:
    """
    Простой FIFO-подобный расчёт средневзвешенной цены по текущему остатку.
    Возвращает (avg_entry_or_None, qty_result).
    Комиссии учитываем только если комиссия в quote (USDT).
    """
    qty = 0.0
    cost = 0.0  # общая себестоимость (в quote)
    for t in trades:
        # поля API MEXC:
        # isBuyer, qty, quoteQty, price, commission, commissionAsset
        side_buy = bool(t.get("isBuyer", False))
        q = float(t.get("qty") or t.get("executedQty") or 0.0)
        p = float(t.get("price") or 0.0)
        quote_q = float(t.get("quoteQty") or (p * q))
        fee = float(t.get("commission") or 0.0)
        fee_asset = (t.get("commissionAsset") or "").upper()

        if side_buy:
            qty += q
            # если комиссия списывалась в USDT — добавим её в себестоимость
            cost += quote_q + (fee if fee_asset in ("USDT", "USD") else 0.0)
        else:
            # продажа уменьшает позицию и позволяет частично списать себестоимость
            if q > qty:
                # редкий случай: продано больше, чем числим — просто обнулим
                q = qty
            if qty > 0:
                avg = cost / qty
                cost -= avg * q
                qty -= q
            # комиссия при продаже в USDT — добавим в расходы для корректной средней, если что-то осталось
            if fee_asset in ("USDT", "USD") and qty > 0:
                cost += fee

    if qty <= 0:
        return None, 0.0
    avg_entry = cost / qty
    return avg_entry, qty


def _iterate_time_windows(days: int, step_days: int = 30) -> List[Tuple[int, int]]:
    now_ms = int(time.time() * 1000)
    res = []
    start_ms = now_ms - days * 24 * 3600 * 1000
    cur = start_ms
    while cur < now_ms:
        end = min(cur + step_days * 24 * 3600 * 1000, now_ms)
        res.append((cur, end))
        cur = end
    return res


def compute_avg_entries(symbols: List[str], lookback_days: int = 180) -> Dict[str, Any]:
    """
    Считает средние входы по списку символов и сохраняет в кэш.
    Возвращает словарь {SYMBOL: {"avg_entry": float|None, "qty_seen": float}}
    """
    result: Dict[str, Any] = {}
    for sym in symbols:
        all_trades: List[Dict[str, Any]] = []
        for start_ms, end_ms in _iterate_time_windows(lookback_days, 30):
            chunk = get_my_trades(sym, start_ms, end_ms, limit=1000)
            if not chunk:
                continue
            all_trades.extend(chunk)

        avg_entry, qty_seen = _calc_avg_from_trades(all_trades)
        result[sym] = {"avg_entry": avg_entry, "qty_seen": qty_seen}

    # запишем автокэш
    cache = load_auto_entries()
    cache.update(result)
    save_auto_entries(cache)
    return result


def get_effective_entry(symbol: str, auto_cache: Dict[str, Any]) -> Optional[float]:
    """
    Возвращает эффективную цену входа:
    1) если задан ручной оверрайд — он главнее
    2) иначе — из автокэша (если есть)
    """
    manual = load_manual_entries()
    sym = symbol.upper()
    if sym in manual:
        return float(manual[sym])
    info = auto_cache.get(sym)
    if not info:
        return None
    return info.get("avg_entry")
