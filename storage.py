# -*- coding: utf-8 -*-
import os
import json
from decimal import Decimal
from typing import Dict

# Здесь максимально простые функции-заглушки.
# Если у тебя уже есть реальные реализации — можешь: либо
# 1) заменить содержимое на вызовы своей логики; либо
# 2) просто подменить код внутри этих функций.

BASE = os.path.dirname(__file__)
ORDERS_LOG = os.path.join(BASE, "orders_log.json")
ENTRIES_MANUAL_JSON = os.path.join(BASE, "entries_manual.json")

# ---------- БАЛАНСЫ ----------
def load_balances() -> Dict[str, str]:
    """
    Верни словарь балансов. Здесь пример-заглушка.
    Если у тебя есть mexc_client.get_account_balances() — используй его.
    """
    # TODO: подключи свою реализацию. Сейчас — пример из твоего сообщения.
    # Возьми живые данные из API при необходимости.
    return {
        # Пример: из твоего текста
        # 'USDT': '50.46811994',
        # 'BLUAI': '5660.48000000',
        # 'FLUXAI': '312944.92000000',
        # 'XLM': '121.02000000',
    }

# ---------- ЦЕНЫ ----------
def load_prices(balances: Dict[str, str]) -> Dict[str, str]:
    """
    Верни цены для <ASSET>USDT. Для USDT цена=1.
    Вставь свою логику обращения к mexc_client / кэшу.
    """
    out = {}
    for asset in balances.keys():
        if asset.upper() == "USDT":
            out["USDT"] = "1"
        else:
            symbol = f"{asset.upper()}USDT"
            p = _get_price_safe(symbol)
            if p is not None:
                out[symbol] = str(p)
    return out

def _get_price_safe(symbol: str) -> Decimal | None:
    try:
        import mexc_client
        if hasattr(mexc_client, "get_price"):
            p = mexc_client.get_price(symbol)
            return Decimal(str(p))
        if hasattr(mexc_client, "get_prices_bulk"):
            prices = mexc_client.get_prices_bulk([symbol])
            p = prices.get(symbol)
            if p is not None:
                return Decimal(str(p))
    except Exception:
        pass
    return None

# ---------- РУЧНЫЕ ВХОДЫ ----------
def load_manual_entries() -> Dict[str, str]:
    if not os.path.exists(ENTRIES_MANUAL_JSON):
        return {}
    try:
        with open(ENTRIES_MANUAL_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            # нормализуем ключи
            return {k.upper(): str(v) for k, v in data.items() if v not in (None, "")}
    except Exception:
        return {}

def save_manual_entry(symbol: str, price: str | None):
    data = load_manual_entries()
    symbol = symbol.upper()
    if price is None:
        # удалить
        if symbol in data:
            del data[symbol]
    else:
        data[symbol] = str(price)
    with open(ENTRIES_MANUAL_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- ВХОДЫ ИЗ ИСТОРИИ ----------
def derive_entries_from_logs(balances: Dict[str, str]) -> Dict[str, str]:
    """
    Средневзвешенный вход по каждому символу из orders_log.json
    Берём только BUY и считаем по формуле:
      avg_price = sum(qty*price) / sum(qty)
    Если лог пустой/нет данных — вернётся {}.
    """
    if not os.path.exists(ORDERS_LOG):
        return {}

    try:
        with open(ORDERS_LOG, "r", encoding="utf-8") as f:
            orders = json.load(f)
    except Exception:
        return {}

    # Считаем по активным балансам
    entries: Dict[str, Decimal] = {}
    qty_sum: Dict[str, Decimal] = {}

    for o in orders:
        try:
            if str(o.get("side", "")).upper() != "BUY":
                continue
            symbol = str(o.get("symbol", "")).upper()
            qty = Decimal(str(o.get("quantity")))
            price = Decimal(str(o.get("price")))
            if qty <= 0 or price <= 0:
                continue

            # если у пользователя нет этого актива сейчас — можно пропустить, но не обязательно
            asset = symbol.replace("USDT", "")
            if balances and Decimal(str(balances.get(asset, "0"))) <= 0:
                # нет позиции — пропускаем (иначе будет «вход» на нулевую позицию)
                continue

            entries[symbol] = entries.get(symbol, Decimal("0")) + qty * price
            qty_sum[symbol] = qty_sum.get(symbol, Decimal("0")) + qty
        except Exception:
            continue

    out: Dict[str, str] = {}
    for symbol, val in entries.items():
        if qty_sum.get(symbol, Decimal("0")) > 0:
            avg = val / qty_sum[symbol]
            out[symbol] = str(avg)
    return out
