import requests
from math import isfinite

API = "https://api.mexc.com"

def _get_24hr_all():
    r = requests.get(f"{API}/api/v3/ticker/24hr", timeout=20, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()
    # отфильтруем только USDT/USDC и валидные числа
    out = []
    for x in data:
        sym = x.get("symbol", "")
        if not (sym.endswith("USDT") or sym.endswith("USDC")):
            continue
        try:
            pct = float(x.get("priceChangePercent", 0))
            volq = float(x.get("quoteVolume", 0))
            last = float(x.get("lastPrice", 0))
            high, low, opn = float(x.get("highPrice", 0)), float(x.get("lowPrice", 0)), float(x.get("openPrice", 0))
        except Exception:
            continue
        if not all(isfinite(v) for v in (pct, volq, last, high, low, opn)):
            continue
        vola = 0.0
        if opn and isfinite(high) and isfinite(low):
            vola = abs(high - low) / opn if opn != 0 else 0.0
        out.append({
            "symbol": sym, "pct": pct, "volq": volq, "last": last, "vola": vola
        })
    return out

def _fmt_row(r):
    return f"{r['symbol']}:  | Δ {r['pct']:.2f}% | V {r['volq']:,} | P {r['last']} | vola {r['vola']:.3f}".replace(",", " ")

def get_market_overview_text():
    rows = _get_24hr_all()
    if not rows:
        return "Нет данных по рынку"

    top_up   = sorted(rows, key=lambda r: r["pct"], reverse=True)[:5]
    top_down = sorted(rows, key=lambda r: r["pct"])[:5]
    top_vol  = sorted(rows, key=lambda r: r["volq"], reverse=True)[:5]
    top_vola = sorted(rows, key=lambda r: r["vola"], reverse=True)[:5]

    parts = []
    parts.append("Топ рост 24ч")
    parts += [_fmt_row(r) for r in top_up]
    parts.append("\nТоп падение 24ч")
    parts += [_fmt_row(r) for r in top_down]
    parts.append("\nТоп объём 24ч")
    parts += [_fmt_row(r) for r in top_vol]
    parts.append("\nТоп волатильность 24ч")
    parts += [_fmt_row(r) for r in top_vola]
    return "\n".join(parts)

def raw_symbols_text():
    rows = _get_24hr_all()
    return "symbols=" + str(len(rows)) + "\n\n" + "\n".join([f"{r['symbol']}:1" for r in rows[:100]])
