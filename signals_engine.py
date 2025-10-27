from typing import List, Dict
from decimal import Decimal
import math

# Пытаемся аккуратно подтянуть витрину рынка из клиента
try:
    from mexc_client import get_24h_all
except Exception:
    get_24h_all = None  # на всякий случай, чтобы не ронять импорт


def _to_dec(x, default="0"):
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


def scan_market_for_signals() -> List[Dict]:
    """
    Возвращает список идей вида:
    {
        "symbol": "BTCUSDT",
        "score": 0.78,               # 0..1
        "reason": "Δ 6.3% | V 1.2e9 | P 111000"
    }

    Логика простая и безопасная:
    - Берём только USDT-пары
    - Считаем грубый скор на основе роста за 24ч и объёма
    - В случае ошибки возвращаем []
    """
    try:
        if get_24h_all is None:
            return []

        data = get_24h_all()
        if not isinstance(data, list):
            return []

        ideas: List[Dict] = []
        for t in data:
            sym = str(t.get("symbol", ""))
            if not sym.endswith("USDT"):
                continue

            ch_pct = _to_dec(t.get("priceChangePercent", "0"))
            qvol = _to_dec(t.get("quoteVolume", "0"))
            last = _to_dec(t.get("lastPrice", "0"))

            # простые эвристики отбора
            if qvol <= 0 or last <= 0:
                continue

            # фильтр по ликвидности (примерно от 1e6 USDT за сутки)
            liquid_ok = qvol >= Decimal("1000000")

            # интересны и рост, и сильные движения
            strong_move = abs(ch_pct) >= Decimal("5")

            if not (liquid_ok and strong_move):
                continue

            # скор: рост даёт +, объём даёт + (логарифмически), ограничиваем 0..0.99
            vol_bonus = min(0.3, Decimal(str(math.log10(float(qvol) + 1))) / Decimal("10"))
            base = Decimal("0.5") + (ch_pct / Decimal("100")) + vol_bonus
            score = float(max(Decimal("0.0"), min(Decimal("0.99"), base)))

            ideas.append({
                "symbol": sym,
                "score": round(score, 3),
                "reason": f"Δ {ch_pct}% | V {qvol} | P {last}"
            })

        # Сортируем по score убыв.
        ideas.sort(key=lambda x: x["score"], reverse=True)
        # Вернём топ-10
        return ideas[:10]

    except Exception:
        # Никогда не роняем бота — просто пусто
        return []
