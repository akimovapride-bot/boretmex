# -*- coding: utf-8 -*-
"""
Формирование текста портфеля в минимальном стиле:
• ASSET: qty
   Цена: price  |  Вход: entry
   P/L: pl
Внизу — строка 💵 USDT: ... (если есть) и итоговая стоимость.
"""

from typing import Dict, List, Tuple
from decimal import Decimal, InvalidOperation

# Используем твои функции из mexc_client и настройки входов
from mexc_client import get_account_info, get_ticker_price

try:
    from settings_manager import load_settings  # ожидается {"entries": {"BTCUSDT": 111000.0, ...}}
except Exception:
    def load_settings():
        return {"entries": {}}


# ---------- утилиты форматирования ----------

def _to_dec(x) -> Decimal:
    try:
        return Decimal(str(x))
    except InvalidOperation:
        return Decimal(0)

def _fmt_thousands(s: str) -> str:
    # заменяем запятые на пробелы для «1 234 567.89»
    return s.replace(",", " ")

def _fmt_qty(x: float) -> str:
    # показываем до 8 знаков (как у тебя было: 312,944.92000000, 5,660.48000000 и т.п.)
    d = _to_dec(x)
    s = f"{d:,.8f}"
    # не убираем нули — именно так было «как раньше»
    return _fmt_thousands(s)

def _fmt_price(x: float) -> str:
    d = _to_dec(x)
    if d == 0:
        return "0"
    # для крупных цен (BTC) — без дробной «лесенки» (как в примере «111 756»),
    # для мелких — до 6 знаков.
    if abs(d) >= 1000:
        s = f"{d:,.0f}"
    elif abs(d) >= 1:
        s = f"{d:,.4f}".rstrip("0").rstrip(".")  # 0.03497 -> "0.03497", 1.2300 -> "1.23"
    else:
        s = f"{d:.6f}".rstrip("0").rstrip(".")
    return _fmt_thousands(s)

def _fmt_money2(x: float) -> str:
    d = _to_dec(x)
    s = f"{d:,.2f}"
    return _fmt_thousands(s)

def _fmt_pl_percent(price: float, entry: float) -> str:
    if entry > 0 and price > 0:
        pct = (price / entry - 1) * 100
        return f"{pct:.2f}%"
    return "n/a"


# ---------- данные ----------

def _collect_balances() -> Dict[str, float]:
    """
    Возвращаем словарь asset -> qty (free+locked), только положительные.
    """
    acc = get_account_info()
    result: Dict[str, float] = {}
    for b in acc.get("balances", []):
        asset = (b.get("asset") or "").upper()
        qty = float(b.get("free", 0) or 0) + float(b.get("locked", 0) or 0)
        if asset and qty > 0:
            result[asset] = result.get(asset, 0.0) + qty
    return result

def _price_usdt(asset: str) -> float:
    if asset.upper() == "USDT":
        return 1.0
    symbol = f"{asset.upper()}USDT"
    try:
        p = get_ticker_price(symbol)
        return float(p or 0.0)
    except Exception:
        return 0.0

def _load_entries_map() -> Dict[str, float]:
    s = load_settings() or {}
    entries = s.get("entries", {}) or {}
    clean = {}
    for k, v in entries.items():
        try:
            clean[str(k).upper()] = float(v)
        except Exception:
            pass
    return clean


# ---------- основной рендер ----------

def calc_portfolio_text() -> str:
    """
    Минимальный вид «как раньше», + поддержка Вход/P&L.
    """
    try:
        balances = _collect_balances()
        if not balances:
            return "📊 Портфель\n\nНет активов на споте."

        entries = _load_entries_map()

        # подготавливаем позиции: (asset, qty, price, cost, entry, pl_usdt)
        rows: List[Tuple[str, float, float, float, float, float]] = []
        for asset, qty in balances.items():
            price = _price_usdt(asset)
            cost = qty * price
            entry = entries.get(f"{asset}USDT", 0.0)
            pl_usdt = qty * (price - entry) if (entry > 0 and price > 0) else 0.0
            rows.append((asset, qty, price, cost, entry, pl_usdt))

        # сортировка «как у тебя визуально получалось» — по стоимости по убыванию,
        # но USDT пусть остаётся отдельной строкой снизу.
        usdt_qty = balances.get("USDT", 0.0)
        body_rows = [r for r in rows if r[0] != "USDT"]
        body_rows.sort(key=lambda r: r[3], reverse=True)

        total = sum(r[3] for r in body_rows) + (usdt_qty * 1.0)

        # рендер позиций
        lines: List[str] = ["📊 Портфель", ""]
        for asset, qty, price, _cost, entry, pl_usdt in body_rows:
            # В минимальном стиле не показываем «Стоимость/Доля» (только как раньше)
            # Блок из трёх строк на актив
            lines.append(f"• {asset}: {_fmt_qty(qty)}")
            lines.append(f"   Цена: {_fmt_price(price)}  |  Вход: {(_fmt_price(entry) if entry > 0 else 'n/a')}")
            if entry > 0 and price > 0:
                pl_pct = _fmt_pl_percent(price, entry)
                lines.append(f"   P/L: {pl_pct} ({_fmt_money2(pl_usdt)} USDT)")
            else:
                lines.append("   P/L: n/a")
            lines.append("")  # пустая строка между активами

        # отдельная строка «💵 USDT: ...» (как у тебя было)
        if usdt_qty > 0:
            lines.append(f"💵 USDT: {_fmt_qty(usdt_qty)}")
            lines.append("")

        # итог
        lines.append(f"💰 Итоговая стоимость: {_fmt_money2(total)} USDT")

        return "\n".join(lines)

    except Exception as e:
        msg = str(e).replace("<", "").replace(">", "")
        return f"Ошибка портфеля: {msg}"
