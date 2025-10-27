#!/usr/bin/env python3
import os
import time
import hmac
import hashlib
from typing import Any, Dict, Optional, List

import httpx
from dotenv import load_dotenv

load_dotenv()

MEXC_BASE_URL = os.getenv("MEXC_BASE_URL", "https://api.mexc.com")
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_API_SECRET = os.getenv("MEXC_API_SECRET")

# --- низкоуровневые помощники -------------------------------------------------

def _ts_ms() -> int:
    return int(time.time() * 1000)

def _sign(params: Dict[str, Any], secret: str) -> str:
    # Строка для подписи — querystring (key=val&key=val...) без URL-эскейпа
    q = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    return hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()

async def _public_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url=MEXC_BASE_URL, timeout=15.0) as client:
        r = await client.get(path, params=params or {})
        r.raise_for_status()
        return r.json()

async def _signed_request(method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not MEXC_API_KEY or not MEXC_API_SECRET:
        raise RuntimeError("Не заданы MEXC_API_KEY / MEXC_API_SECRET в .env")

    p = dict(params or {})
    p.setdefault("recvWindow", 5000)
    p.setdefault("timestamp", _ts_ms())
    signature = _sign(p, MEXC_API_SECRET)
    p["signature"] = signature

    headers = {"X-MEXC-APIKEY": MEXC_API_KEY}
    async with httpx.AsyncClient(base_url=MEXC_BASE_URL, timeout=20.0, headers=headers) as client:
        if method.upper() == "GET":
            r = await client.get(path, params=p)
        elif method.upper() == "POST":
            # MEXC v3 — параметры в query, тело пустое (как у Binance)
            r = await client.post(path, params=p)
        else:
            raise ValueError("Unsupported method")
        r.raise_for_status()
        return r.json()

# --- ПУБЛИЧНАЯ ЦЕНА -----------------------------------------------------------

async def get_price(symbol: str) -> Optional[float]:
    """
    Возвращает последнюю цену символа (например, 'BTCUSDT').
    Для 'USDT' вернёт 1.0. Если цены нет — None.
    """
    s = symbol.upper()
    if s in ("USDT", "USDTUSDT"):
        return 1.0
    try:
        data = await _public_get("/api/v3/ticker/price", {"symbol": s})
        # Ответ вида: {"symbol":"BTCUSDT","price":"111111.11"}
        px = float(data.get("price"))
        return px
    except Exception:
        return None

# --- БАЛАНСЫ ------------------------------------------------------------------

async def get_account_balances() -> List[Dict[str, Any]]:
    """
    Возвращает список балансов в форме:
    [{"asset":"BTC","free":"0.001","locked":"0.0"}, ...]
    """
    data = await _signed_request("GET", "/api/v3/account", {})
    # Совместимо с binance-style ответом
    balances = data.get("balances") or data.get("data") or data.get("assets") or []
    # Нормализуем ключи
    norm = []
    for b in balances:
        asset = b.get("asset") or b.get("currency") or b.get("symbol")
        free = b.get("free") or b.get("available") or b.get("availableBalance") or b.get("balance")
        locked = b.get("locked") or b.get("frozen") or "0"
        if asset and free is not None:
            try:
                _free = float(free)
                _locked = float(locked) if locked is not None else 0.0
            except Exception:
                continue
            norm.append({"asset": asset.upper(), "free": _free, "locked": _locked})
    return norm

# --- РАЗМЕЩЕНИЕ ОРДЕРА --------------------------------------------------------

async def place_order(
    symbol: str,
    side: str,
    type_: str,
    quantity: float,
    price: Optional[float] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Размещает ордер. Для MARKET BUY/SELL достаточно symbol/side/type_/quantity.
    Для LIMIT можно передать price, timeInForce=GTC и т.п. через kwargs.
    """
    params: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "side": side.upper(),           # BUY / SELL
        "type": type_.upper(),          # MARKET / LIMIT / ...
        "quantity": f"{quantity:.8f}",
        "newOrderRespType": "RESULT",
    }
    if price is not None:
        params["price"] = str(price)
    params.update(kwargs or {})

    return await _signed_request("POST", "/api/v3/order", params)
