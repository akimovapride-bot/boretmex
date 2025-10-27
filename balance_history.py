from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple
import requests
import math

API = "https://api.mexc.com"
STORAGE_DIR = Path("storage")
ENTRIES_FILE = STORAGE_DIR / "entries.json"   # средняя цена входа по активам

def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not ENTRIES_FILE.exists():
        ENTRIES_FILE.write_text("{}", encoding="utf-8")

def load_entries() -> Dict[str, float]:
    _ensure_storage()
    try:
        return json.loads(ENTRIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_entry(asset: str, price: float):
    d = load_entries()
    d[asset.upper()] = float(price)
    ENTRIES_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def _price(symbol: str) -> float:
    r = requests.get(f"{API}/api/v3/ticker/price",
                     params={"symbol": symbol},
                     timeout=15,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return float(r.json()["price"])

def _fmt_num(x: float, max_dp: int = 8) -> str:
    if x is None or math.isnan(x) or math.isinf(x):
        return "n/a"
    # умный формат: для больших — 2 знака, для мелких — до 8
    if x >= 1000:
        return f"{x:,.2f}".replace(",", " ")
    if x >= 1:
        return f"{x:,.2f}".replace(",", " ")
    # мелкие числа — до 8 знаков, без лишних нулей
    s = f"{x:.8f}".rstrip("0").rstrip(".")
    return s

def _calc_pl(current: float, entry: float, qty: float) -> Tuple[float, float]:
    if not entry or entry <= 0:
        return (float("nan"), float("nan"))
    pct = (current - entry) / entry * 100
    usdt = (current - entry) * qty
    return pct, usdt

def calc_portfolio_text() -> str:
    """
    Использует твой mexc_client.get_account_info() и отображает активы красиво.
    P/L берётся из storage/entries.json (заводится автоматически сделками через бота).
    """
    try:
        from mexc_client import get_account_info
        account = get_account_info()
        balances = account.get("balances") or account
    except Exception as e:
        return f"Портфель\n\nНе удалось получить активы: {e}"

    entries = load_entries()

    # Собираем активы
    items = []  # (asset, free, price, value_usdt, entry_price, pl_pct, pl_usdt)
    total_usdt = 0.0

    for b in balances:
        free = float(b.get("free", 0) or b.get("available", 0) or 0)
        asset = (b.get("asset") or b.get("currency") or "").upper()
        if not asset or free <= 0:
            continue

        if asset in ("USDT", "USDC"):
            total_usdt += free
            items.append((asset, free, 1.0, free, entries.get(asset), float("nan"), float("nan")))
            continue

        symbol = f"{asset}USDT"
        try:
            p = _price(symbol)
            value = free * p
            total_usdt += value
            entry = entries.get(asset)
            pl_pct, pl_usdt = _calc_pl(p, entry, free) if entry else (float("nan"), float("nan"))
            items.append((asset, free, p, value, entry, pl_pct, pl_usdt))
        except Exception:
            # нет прямой пары — пропустим
            continue

    if not items:
        return "Портфель\n\nУ тебя нет активов или их не удалось получить."

    # скрыть пыль (< 0.5 USDT), кроме стейблов
    filtered = []
    for it in items:
        asset, free, price, value, entry, pl_pct, pl_usdt = it
        if asset in ("USDT", "USDC") or value >= 0.5:
            filtered.append(it)

    # сортировка по стоимости
    filtered.sort(key=lambda x: x[3], reverse=True)

    lines: List[str] = []
    lines.append("📊 <b>Портфель</b>\n")

    for asset, free, price, value, entry, pl_pct, pl_usdt in filtered:
        if asset in ("USDT", "USDC"):
            lines.append(f"💵 <b>{asset}</b>: {_fmt_num(free)}")
            continue

        entry_txt = _fmt_num(entry) if entry else "n/a"
        pl_line = "P/L: n/a"
        if entry and entry > 0:
            pp = "n/a" if math.isnan(pl_pct) else f"{pl_pct:.2f}%"
            uu = "n/a" if math.isnan(pl_usdt) else f"{_fmt_num(pl_usdt)} USDT"
            sign = "🟢" if (not math.isnan(pl_usdt) and pl_usdt >= 0) else "🔴"
            pl_line = f"{sign} P/L: {pp} ({uu})"

        lines.append(
            f"• <b>{asset}</b>: {_fmt_num(free)}\n"
            f"   Цена: {_fmt_num(price)}  |  Вход: {entry_txt}\n"
            f"   {pl_line}"
        )

    lines.append(f"\n💰 <b>Итоговая стоимость</b>: {_fmt_num(total_usdt)} USDT")
    return "\n".join(lines)
