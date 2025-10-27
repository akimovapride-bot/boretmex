# orders.py
import os
import time
import hmac
import hashlib
import math
from typing import Optional, Tuple, Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MEXC_API_KEY", "")
API_SECRET = os.getenv("MEXC_SECRET_KEY", "")
LIVE_ARM = os.getenv("LIVE_ARM", "0").strip() == "1"

BASE = "https://api.mexc.com"  # рабочий домен API
TIMEOUT = 15


class MexcError(RuntimeError):
    pass


def _sign(params: Dict[str, Any]) -> str:
    query = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()


def _public_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE}{path}"
    r = requests.get(url, params=params or {}, timeout=TIMEOUT)
    if r.status_code != 200:
        raise MexcError(f"{r.status_code} {r.text}")
    data = r.json()
    return data


def _signed_request(method: str, path: str, params: Dict[str, Any]) -> Any:
    if not API_KEY or not API_SECRET:
        raise MexcError("Не заданы MEXC_API_KEY / MEXC_SECRET_KEY в .env")
    ts = int(time.time() * 1000)
    params = dict(params or {})
    params["timestamp"] = ts
    params["recvWindow"] = 5000
    sig = _sign(params)
    params["signature"] = sig

    url = f"{BASE}{path}"
    headers = {"X-MEXC-APIKEY": API_KEY}

    if method.upper() == "GET":
        r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
    elif method.upper() == "POST":
        r = requests.post(url, params=params, headers=headers, timeout=TIMEOUT)
    else:
        raise MexcError("Unsupported method")

    if r.status_code != 200:
        raise MexcError(f"{r.status_code} {r.text}")
    return r.json()


def get_symbol_filters(symbol: str) -> Tuple[float, float, float]:
    """
    Возвращает (price_tick, qty_step, min_notional) для символа.
    """
    info = _public_get("/api/v3/exchangeInfo", {"symbol": symbol})
    symbols = info.get("symbols", [])
    if not symbols:
        raise MexcError(f"exchangeInfo: символ {symbol} не найден")
    s = symbols[0]

    price_tick = 0.0
    qty_step = 0.0
    min_notional = 0.0

    for f in s.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            price_tick = float(f.get("tickSize", "0"))
        elif f.get("filterType") == "LOT_SIZE":
            qty_step = float(f.get("stepSize", "0"))
        elif f.get("filterType") == "NOTIONAL":
            min_notional = float(f.get("minNotional", "0"))

    # подстрахуемся, если что-то не пришло
    if price_tick == 0:
        price_tick = 0.00000001
    if qty_step == 0:
        qty_step = 0.00000001
    return price_tick, qty_step, min_notional


def round_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step) * step


def round_to_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return value
    return round(round(value / tick) * tick, max(0, -int(math.log10(tick))) if tick < 1 else 0)


def get_price(symbol: str) -> float:
    data = _public_get("/api/v3/ticker/price", {"symbol": symbol})
    return float(data["price"])


def get_account_balances() -> Dict[str, float]:
    data = _signed_request("GET", "/api/v3/account", {})
    balances = {}
    for b in data.get("balances", []):
        free = float(b.get("free", "0"))
        locked = float(b.get("locked", "0"))
        total = free + locked
        if total > 0:
            balances[b["asset"]] = total
    return balances


def preview_market_buy(symbol: str, budget_usdt: float, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]:
    """
    Возвращает предпросмотр: текущая цена, рассчитанное количество, округление по шагам, нотацион.
    """
    px = get_price(symbol)
    price_tick, qty_step, min_notional = get_symbol_filters(symbol)

    qty_raw = budget_usdt / px
    qty = round_to_step(qty_raw, qty_step)

    notional = qty * px
    if notional < min_notional:
        # увеличим qty до минимума, если возможно
        need_qty = min_notional / px
        qty = round_to_step(need_qty, qty_step)
        notional = qty * px

    return {
        "symbol": symbol,
        "price": round_to_tick(px, price_tick),
        "qty": qty,
        "notional": notional,
        "sl": sl,
        "tp": tp,
        "live": LIVE_ARM,
    }


def place_market_buy(symbol: str, budget_usdt: float, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]:
    """
    Выполнить MARKET покупку на MEXC на сумму budget_usdt (в USDT).
    Возвращает ответ биржи и echo SL/TP (бот их хранит/использует сам).
    """
    preview = preview_market_buy(symbol, budget_usdt, sl, tp)
    qty = preview["qty"]
    if qty <= 0:
        raise MexcError("Рассчитанное количество = 0. Увеличь бюджет или проверь символ.")

    if not LIVE_ARM:
        # демо-режим — просто вернём предпросмотр
        preview["status"] = "DRY_RUN"
        return preview

    params = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "quantity": f"{qty:.10f}",
    }
    res = _signed_request("POST", "/api/v3/order", params)
    return {
        "status": "FILLED",
        "order": res,
        "sl": sl,
        "tp": tp,
        "preview": preview,
    }
